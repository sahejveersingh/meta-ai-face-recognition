# Backend Service for Meta AI Glasses Face Recognition

## Features
- Accepts video uploads (e.g., from livestream recordings)
- Detects faces in video frames
- Crops and saves face images
- Mocks PimEyes and GPT profile summaries
- Provides API endpoints for uploading videos and fetching profiles

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the backend server:
   ```bash
   uvicorn backend.main:app --reload
   ```

## API Endpoints

- `POST /upload-video/` — Upload a video file for face detection and profile summary extraction.
- `GET /profiles/` — Get the latest detected (mocked) profiles.

## Notes
- This is a prototype. PimEyes and GPT responses are mocked.
- For real-time livestream processing, see the README for future instructions.

## Real-Time Stream Processing (Prototype)

You can process a video stream in real time using the `/process-stream/` endpoint. This works with:
- A video file that is being written to (e.g., by OBS Studio)
- A stream URL (e.g., RTMP/RTSP, if available)

### Using OBS Studio to Record or Stream Your Instagram Live

1. **Install OBS Studio:** https://obsproject.com/
2. **Open your Instagram Live in a browser window.**
3. **In OBS, add a new "Window Capture" source** and select your browser window.
4. **Set OBS to record to a file:**
   - Go to Settings > Output > Recording, set the path (e.g., `/tmp/insta_live.mp4`).
   - Start Recording.
5. **Call the backend endpoint:**
   - Use the `/process-stream/` endpoint with the file path:
     ```bash
     curl -X POST "http://localhost:8000/process-stream/?video_path=/tmp/insta_live.mp4"
     ```
   - The backend will process frames as they are written to the file.

**Note:** For true real-time, you can also set up OBS to stream to a local RTMP server and use the RTMP URL as `video_path`.

## OpenAI API Key Setup (for LLM Summarization)

1. Create a file called `.env` in your `backend` directory.
2. Add your OpenAI API key to the file like this:
   ```
   OPENAI_API_KEY=sk-...
   ```
3. The backend will use this key to call the OpenAI API for profile summarization. 