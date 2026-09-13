# Eco-Router — Voice AI Guide

## Overview

Eco-Router includes a voice interface powered by the browser's native Web Speech API.
No audio is sent to the backend. Only the transcribed text reaches the AI endpoint.

## How It Works

`
VOICE INPUT (microphone)
        |
Browser Web Speech API (speech-to-text, LOCAL)
        |
Transcribed text
        |
POST /ai/ask
        |
AI Orchestrator
        |
Answer text
        |
Browser speechSynthesis (text-to-speech, LOCAL)
`

## UI States

| State | Description |
|---|---|
| IDLE | Ready to listen |
| LISTENING | Microphone active, recording |
| PROCESSING | Text sent to AI, awaiting response |
| ANSWERING | Speaking the AI response |
| UNAVAILABLE | Browser does not support Web Speech API |

## Browser Support

| Browser | Status |
|---|---|
| Chrome / Edge | Supported |
| Firefox | Not supported (use text input) |
| Safari | Partial support |

If voice is unavailable, a text input fallback is always shown.

## Voice Buttons

- Hero section: **ASK ECO INTELLIGENCE** — starts listening for a question
- AI Console section: **VOICE** button — alternative entry point

## Example Questions

- "Why was Europe selected?"
- "Which region is currently cleanest?"
- "What are the carbon intensity trends?"
- "How much potential savings are we estimating?"
- "How is infrastructure health?"

## Security & Privacy

- Audio is processed by the browser locally — not sent to the backend
- Only the transcribed text string is sent to /ai/ask
- No voice recordings are stored
- No voice transcripts are persisted in the database
- The AI cannot trigger infrastructure changes via voice input

## Accessibility

- Voice buttons have aria-label attributes
- Keyboard accessible (Enter/Space to activate)
- Visible focus state
- Text input always available as fallback
- Voice state clearly displayed in the UI
