# Textractor to speech CLI

A python app to  extract core text from a PDF and generate a AI voiced reading of it. 

Designed for mainly scientific papers with lots of citations and footnotes, which make blanket text to speech techniques clunky. The 'textractor' uses text location and regex to find clutter and citations, removes them and returns what should be the core text of the paper.
It then offers a manual review before offering to use googles text-to-speech API to generate a .mp3 file of it. 

Currently the AI voice in use is from Chirp 3 HD, Aoede, but might update to have a UI selector for these. One can just manually change it in the code too, of course. 

## Prerequisites

* Python 3.7 + pip 
* A Google Cloud Platform (GCP) account with billing enabled

## Setup Instructions

Follow these steps to get the tool running on your local machine.

1. Clone the RepositoryOpen your terminal and clone this project from GitHub
2. Install Dependencies (recommend to use a Python virtual environment to keep your project dependencies isolated)
   * Create a virtual environment
     ```python3 -m venv venv```
   * Activate the environment
     * On Linux/macOS/WSL:
       ```source venv/bin/activate```
     * On Windows:
       ``` .\venv\Scripts\activate```
    * Install required packages
      ```pip install -r requirements.txt```

3. Get Google Cloud Credentials 
  * This script requires a Service Account Key to securely connect to the Google Cloud Text-to-Speech API. This is a one-time setup.
    * Go to the Google Cloud Console and select your project.
    * Navigate to the Text-to-Speech API library (on 26.06.25 this link worked: https://console.cloud.google.com/apis/library/texttospeech.googleapis.com)
    * Click the blue ENABLE button if it is not already enabled.
    * Click on MANAGE.
    * Find and click on "+ Create Credentials" (on the righthand side of the page), select "Service Account"
    * Give the service account a representative name (easier to find and manage in the future) and click CREATE AND CONTINUE.
    * Once created, you should be back on the list of service accounts (on 26.06.25 this link worked: https://console.cloud.google.com/iam-admin/serviceaccounts).
    * Find the one you created and click on its email address.
    * Navigate to the KEYS tab, click ADD KEY -> Create new key.
      * Choose JSON as the key type and click CREATE. A JSON file will be downloaded.
    * Rename the downloaded JSON file to "google-credentials.json" and move it into the root directory of this project.
      * The .gitignore file is already configured to ignore this file, so you won't accidentally commit it. 

NB: The process of getting a suitable service account and its credentials could change in time, and some sources describe the process differently - this worked well enough for me. Google Cloud is complex... 

## How to use:

Once the setup is complete, you can run the main script from your terminal:

```python text_to_speech_suite.py```

or 

```python3 text_to_speech_suite.py```

The script will guide you through the rest of the process.


