# Privacy and local-data boundaries

YOEAI is local-first. With a loopback llama.cpp backend, prompts and submitted images are processed on the configured PC. Selecting a different endpoint changes that boundary; verify configuration yourself.

## Stored on your PC
Conversation history, agent task history, preferences, memory, reports and technical logs may persist in the configured Windows profile. Logs can contain local paths and error details. Local files are subject to Windows account permissions and backups. Use the application's history/memory controls to remove unwanted records; deleting an entry does not erase external backups. Back up the profile before updates.

## Features that use a network
- Enabled web search sends your search query to the configured search service. Opening result pages contacts those sites; they have their own policies. Do not include secrets in queries.
- Explicit model/runtime downloads contact their configured distribution hosts. Review the origin, license and destination first.
- Website visits, support email, optional project-support payments and GitHub are separate services. This repository does not provide their privacy controls.

Do not assume an optional adapter is offline merely because the chat model is local. Review its configuration and permitted tools.

## Microphone and files
Voice capture begins through an explicit microphone/session action. The documented configured speech pipeline is local; workers/model files are separately installed. End or mute the session when finished. Selected files, screenshots and application text may contain sensitive information. Grant scoped access only to content you intend to process. Transcription does not itself approve a Windows command or a message submission.

## Before sharing a bug report
Remove names, local paths, chat content, screenshots, tokens, credentials and device identifiers you do not want public. Never upload private profiles, binaries or model weights merely to reproduce an issue. Privacy questions can use the contact in SECURITY.md. This is technical source-preview information, not a promise that every external service is private or offline.
