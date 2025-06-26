# Meta AI Face Dashboard (Frontend)

This is a simple React dashboard to display detected profiles from the backend service.

## Setup

1. Install dependencies:
   ```bash
   npm install
   ```

2. Start the development server:
   ```bash
   npm start
   ```

3. The app will run at [http://localhost:3000](http://localhost:3000) by default.

## Features
- Polls the backend every 5 seconds for new detected profiles
- Displays name, location, social profiles, and connections

## Notes
- Make sure the backend is running at `http://localhost:8000` (default) or update the API URL in `src/App.js` if needed. 