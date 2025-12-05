# Google OAuth Setup Guide

## Required API Keys

To implement Google OAuth authentication, you need the following:

### 1. Google OAuth 2.0 Client ID
- **Environment Variable**: `GOOGLE_CLIENT_ID`
- **Where to get it**: 
  1. Go to [Google Cloud Console](https://console.cloud.google.com/)
  2. Create a new project or select an existing one
  3. Enable the Google+ API (or Google Identity API)
  4. Go to "Credentials" → "Create Credentials" → "OAuth 2.0 Client ID"
  5. Configure OAuth consent screen
  6. Create OAuth 2.0 Client ID for "Web application"
  7. Add authorized redirect URIs:
     - `http://localhost:3000/api/auth/google/callback` (development)
     - `https://yourdomain.com/api/auth/google/callback` (production)
  8. Copy the Client ID

### 2. Google OAuth 2.0 Client Secret
- **Environment Variable**: `GOOGLE_CLIENT_SECRET`
- **Where to get it**: 
  - Same place as Client ID (Google Cloud Console → Credentials)
  - Copy the Client Secret (keep this secure!)

## Environment Variables to Add

Add these to your backend `.env` file:

```bash
# Google OAuth
GOOGLE_CLIENT_ID=your_google_client_id_here
GOOGLE_CLIENT_SECRET=your_google_client_secret_here
```

Add this to your frontend `.env.local` file:

```bash
# Google OAuth (for frontend redirect)
NEXT_PUBLIC_GOOGLE_CLIENT_ID=your_google_client_id_here
```

## Implementation Notes

- Currently, the app uses a mock OAuth flow for development
- In production, you'll need to implement the full OAuth redirect flow:
  1. User clicks "Continue with Google"
  2. Redirect to Google OAuth consent screen
  3. User authorizes
  4. Google redirects back with authorization code
  5. Exchange code for access token
  6. Get user info from Google
  7. Send to backend `/api/auth/oauth/callback`

## OAuth Providers Removed

- ❌ GitHub OAuth - Removed
- ❌ Twitter/X OAuth - Removed
- ✅ Google OAuth - Only supported provider

