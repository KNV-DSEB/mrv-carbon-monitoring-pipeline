# Google Earth Engine access setup

The data collection module (`src/mrv/data_collection/`) reads Sentinel-2
imagery through the Google Earth Engine (GEE) Python API. This needs a
Google Cloud project registered for Earth Engine, plus a service account so
the pipeline can authenticate non-interactively.

## 1. Sign up for Earth Engine

1. Go to https://earthengine.google.com/ and sign up for non-commercial /
   research use (free tier — this is what we're using, per the local-only
   compute decision in [CLAUDE.md](../../CLAUDE.md)).
2. Approval is usually near-instant for a personal Google account.

## 2. Create (or reuse) a Google Cloud project

1. In the [Google Cloud Console](https://console.cloud.google.com/), create a
   new project (or reuse one) — this becomes `GEE_PROJECT_ID` in `.env`.
2. Enable the **Earth Engine API** for that project (Cloud Console →
   "APIs & Services" → "Enable APIs and Services" → search "Earth Engine API").

## 3. Create a service account for non-interactive auth

The pipeline should authenticate as a service account (not your personal
Google login), so it can run unattended.

1. Cloud Console → "IAM & Admin" → "Service Accounts" → "Create Service
   Account" in the same project.
2. Grant it the **Earth Engine Resource Viewer** role (read-only is enough
   for querying/exporting imagery).
3. Create a JSON key for the service account and download it.
4. **Do not put this key inside the repo.** Store it somewhere outside the
   working tree and set `GEE_SERVICE_ACCOUNT_KEY_PATH` in `.env` to its
   absolute path.
5. Register the service account for Earth Engine access: it must be added at
   https://signup.earthengine.google.com/ (or via the Earth Engine
   registration flow linked from your Cloud project) the same way a user
   account is registered — service accounts need explicit EE enablement too.

## 4. Verify access

Once `earthengine-api` is installed (module 1 will add this to
`requirements.txt`), authentication in code looks like:

```python
import ee

credentials = ee.ServiceAccountCredentials(
    email=None,  # read from the key file itself
    key_file=os.environ["GEE_SERVICE_ACCOUNT_KEY_PATH"],
)
ee.Initialize(credentials, project=os.environ["GEE_PROJECT_ID"])
```

A successful `ee.Initialize()` with no exception confirms the setup is
working. This verification step will be part of module 1's unit tests
(mocked where it would otherwise require live network/credentials in CI).
