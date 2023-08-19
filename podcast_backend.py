import modal

def download_whisper():
  # Load the Whisper model
  import os
  import whisper
  print ("Download the Whisper model")

  # Perform download only once and save to Container storage
  whisper._download(whisper._MODELS["medium"], '/content/podcast/', False)


stub = modal.Stub("corise-podcast-project")
corise_image = modal.Image.debian_slim().pip_install("feedparser",
                                                     "https://github.com/openai/whisper/archive/9f70a352f9f8630ab3aa0d06af5cb9532bd8c21d.tar.gz",
                                                     "requests",
                                                     "ffmpeg",
                                                     "openai",
                                                     "tiktoken",
                                                     "wikipedia",
                                                     "ffmpeg-python").apt_install("ffmpeg").run_function(download_whisper)


@stub.function(image=corise_image, gpu="any", timeout=600)
def get_podcast_feed(rss_url):
  print ("Reading full podcast feed")
  print ("Feed URL: ", rss_url)

  # Read from the RSS Feed URL
  import feedparser
  intelligence_feed = feedparser.parse(rss_url)
  podcast_title = intelligence_feed['feed']['title']
  podcast_link = intelligence_feed['feed']['link']
  podcast_image = intelligence_feed['feed']['image'].href
  podcast_feed = []
  for item in intelligence_feed.entries:
    episode_title = item['title']
    episode_date = item['published']
    try:
      season = item ['itunes_season']
    except:
      season = ''

    try:
      episode = item ['itunes_episode']
    except:
      episode = ''
    for item in item.links:
      if (item['type'] == 'audio/mpeg'):
        episode_audio_url = item.href
    podcast_feed.append({
      "podcast_title": podcast_title,
      "podcast_link": podcast_link,
      "podcast_image": podcast_image,
      "episode_title": episode_title,
      "episode_date": episode_date,
      "episode_season": season,
      "episode_episode": episode,
      "episode_audio_url": episode_audio_url
    })
  print ("RSS URL Read: ", podcast_feed)
  return podcast_feed


@stub.function(image=corise_image, gpu="any", timeout=600)
def get_transcribe_podcast(podcast_feed_item, local_path):
  episode_title = podcast_feed_item['episode_title']
  episode_name = f"{episode_title}.mp3"
  print ("Starting Podcast Transcription Function")
  print ("Item: ", episode_title)
  print ("Local Path:", local_path)

  episode_url = podcast_feed_item['episode_audio_url']

  # Download the podcast episode by parsing the RSS feed
  from pathlib import Path
  p = Path(local_path)
  p.mkdir(exist_ok=True)

  print ("Downloading the podcast episode")
  import requests
  with requests.get(episode_url, stream=True) as r:
    r.raise_for_status()
    episode_path = p.joinpath(episode_name)
    with open(episode_path, 'wb') as f:
      for chunk in r.iter_content(chunk_size=8192):
        f.write(chunk)

  print ("Podcast Episode downloaded")

  # Load the Whisper model
  import os
  import whisper

  # Load model from saved location
  print ("Load the Whisper model")
  model = whisper.load_model('medium', device='cuda', download_root='/content/podcast/')

  # Perform the transcription
  print ("Starting podcast transcription")
  result = model.transcribe(local_path + episode_name)

  # Return the transcribed text
  print ("Podcast transcription completed, returning results...")
  output = {}
  podcast_feed_item['episode_transcript'] = result['text']
  return podcast_feed_item

@stub.function(image=corise_image, secret=modal.Secret.from_name("my-openai-secret"))
def get_podcast_summary(podcast_feed_item):
  import openai
  instructPrompt = "create a tl;dr summary of this podcast, with 1-3 bullet points"
  request = instructPrompt + podcast_feed_item['episode_transcript']

  chatOutput = openai.ChatCompletion.create(model="gpt-3.5-turbo-16k",
                                            messages=[{"role": "system", "content": "You are a helpful assistant."},
                                                      {"role": "user", "content": request}
                                                      ]
                                            )
  podcastSummary = chatOutput.choices[0].message.content
  podcast_feed_item['episode_summary'] = podcastSummary
  return podcast_feed_item

@stub.function(image=corise_image, secret=modal.Secret.from_name("my-openai-secret"))
def get_podcast_characters(podcast_feed_item):
  import openai
  import wikipedia
  import json

  podcast_transcript = podcast_feed_item['episode_transcript']
  request = podcast_transcript

  #extract podcast_characters
  completion = openai.ChatCompletion.create(
    model="gpt-3.5-turbo-16k",
    messages=[{"role": "user", "content": request}],
    functions=[
    {
      "name": "list_podcast_characters",
      "description": "Lists the name of characters discussed on this podcast" +
        "Returns an array of characters.",
      "parameters": {
        "type": "object",
        "properties": {
          "list": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "character_name": {
                  "description": "The name of a character."
                },
                "character_description": {
                    "description": "A one sentence description of the character"
                }
              },
              "description": "A character discussed on the podcast."
            },
            "description": "Array of characters discussed on the podcast."
          }
        }
      }
    }
    ],
    function_call={"name": "list_podcast_characters"}
    )

  #grab podcast characters
  podcast_characters = []
  response_message = completion["choices"][0]["message"]
  if response_message.get("function_call"):
    function_name = response_message["function_call"]["name"]
    function_args = json.loads(response_message["function_call"]["arguments"])
    podcast_characters=function_args.get("list")

  # augement with wikipedia descriptions
  for character in podcast_characters:
    try:
      input = wikipedia.page(character["character_name"], auto_suggest=False)
    except:
      character["wikipedia"] = ""
    else:
      character["wikipedia"] = input.summary
      # TODO: grab image

  podcast_feed_item['episode_characters'] = podcast_characters
  return podcast_feed_item

@stub.function(image=corise_image, secret=modal.Secret.from_name("my-openai-secret"))
def get_podcast_highlights(podcast_feed_item):
  import openai

  podcast_transcript = podcast_feed_item['episode_transcript']

  instructPrompt = "Break this podcast into chapters & key moments, with a timestamp and description of moment. Return the chapter sections & highlights  in markdown."

  request = instructPrompt + podcast_transcript

  chatOutput = openai.ChatCompletion.create(model="gpt-3.5-turbo-16k",
                                            messages=[{"role": "system", "content": "You are a helpful assistant."},
                                                      {"role": "user", "content": request}
                                                      ]
                                            )
  podcastHighlights = chatOutput.choices[0].message.content

  podcast_feed_item['episode_highlights'] = podcastHighlights

  return podcast_feed_item

#TODO function to generate quiz on podcast info

@stub.function(image=corise_image, secret=modal.Secret.from_name("my-openai-secret"), timeout=1200)
def process_podcast_episode(podcast_details, path):
  output = {}
  podcast_details = get_transcribe_podcast.call(podcast_details, path)
  podcast_details = get_podcast_summary.call(podcast_details)
  podcast_details = get_podcast_characters.call(podcast_details)
  podcast_details = get_podcast_highlights.call(podcast_details)
  return podcast_details

# TODO REMOVE
@stub.function(image=corise_image, secret=modal.Secret.from_name("my-openai-secret"), timeout=1200)
def process_podcast(url, path):
  output = {}
  podcast_feed = get_podcast_feed(url)
  podcast_details = get_transcribe_podcast.call(podcast_feed[0], path)
  podcast_details = get_podcast_summary.call(podcast_details)
  podcast_details = get_podcast_characters.call(podcast_details)
  podcast_details = get_podcast_highlights.call(podcast_details)
  return podcast_details

@stub.local_entrypoint()
def test_method(url, path):
  output = {}
  podcast_feed = get_podcast_feed(url)
  podcast_details = podcast_feed[0]
  podcast_details = process_podcast_episode(podcast_details, path)
  print ("Podcast Details: ", podcast_details)
