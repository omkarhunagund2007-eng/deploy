# deploy

Flask quiz app configured for Vercel deployment.

## Vercel setup

Set these environment variables in the Vercel project before deploying:

- `MONGODB_URI`: MongoDB connection string
- `DB_NAME`: MongoDB database name, defaults to `quiz`
- `SECRET_KEY`: Flask session secret

Vercel uses `vercel.json` to route all requests to `server.py`, where the top-level Flask `app` is exported.
