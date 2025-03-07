# Call Analysis Tool

## Overview

The **Call Analysis Tool** is a Flask-based web application that processes and analyzes call recordings. It transcribes the audio, detects the language, scores the call based on predefined criteria, and provides suggestions for improvement.

## Features

- Upload and analyze call recordings
- Transcription of audio files
- Language detection
- Call scoring based on predefined metrics
- Suggestions for improvement

## Prerequisites

Ensure you have the following installed on your system:

- Python 3.x
- Flask
- Required Python libraries (see `requirements.txt`)

## Installation

1. Clone the repository:
   ```sh
   git clone https://github.com/your-repo/call-analysis-tool.git
   cd call-analysis-tool
   ```
2. Create a virtual environment (optional but recommended):
   ```sh
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```
3. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```

## Usage

1. Run the Flask application:
   ```sh
   python app.py
   ```
2. Open your browser and navigate to `http://127.0.0.1:5000`
3. Upload an audio file and analyze the call

## API Endpoints

| Endpoint      | Method | Description                                      |
| ------------- | ------ | ------------------------------------------------ |
| `/`           | GET    | Home page                                        |
| `/upload`     | POST   | Upload an audio file for analysis                |
| `/transcribe` | POST   | Transcribes the uploaded audio file              |
| `/analyze`    | POST   | Analyzes the transcription and provides feedback |

## Configuration

You can configure different settings such as scoring parameters, languages supported, and improvement criteria in the application's configuration files.

## Dependencies

Ensure the following Python packages are installed:

- Flask
- SpeechRecognition
- langdetect
- TextBlob

Install them using:

```sh
pip install -r requirements.txt
```

## Contributing

If you'd like to contribute, please fork the repository and submit a pull request with your improvements.

##

