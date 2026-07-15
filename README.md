# Nebissi — payment ledger (Django)

Admin-only web app for tracking payments at Nebissi cyber café: photocopying,
printing, scanning, and any other service you add. Built with Django +
SQLite, so everything runs locally with no external services.

## What's inside

- **Overview** — today's total, this week's total, all-time total, and a
  revenue-by-service breakdown.
- **New payment** — pick a service, its default price fills in automatically,
  set quantity, and the total is calculated for you (still editable).
- **Ledger** — every payment, filterable by service / date range / search
  text, with CSV export.
- **Services** — add, reprice, deactivate, or remove services.
- **Django admin** (`/admin/`) — full raw database access if you ever need it.
- Login required on every page — only your admin account can see payments.

## First-time setup (Windows / PowerShell)

Your terminal history shows two issues worth avoiding:

1. Your folder was named `NEBISSI .1` (with a space). PowerShell splits
   unquoted paths on spaces, so `cd NEBISSI .1` fails. Either rename the
   folder to remove the space (recommended, e.g. `Nebissi`), or always quote
   it: `cd "NEBISSI .1"`.
2. `manage.py` only exists inside this project folder. If you `cd` up a
   level (`cd ..`) and then run `python manage.py runserver`, Python won't
   find it — you have to be inside the folder that contains `manage.py`.

Here's the full setup from a clean folder. Pick a path with **no spaces**,
e.g. `C:\Users\user\Projects\Nebissi`.

```powershell
# 1. Go to (or create) a folder with no spaces in the path
mkdir C:\Users\user\Projects
cd C:\Users\user\Projects

# 2. Unzip this project here, so you have:
#    C:\Users\user\Projects\nebissi\manage.py

cd nebissi

# 3. Create and activate a virtual environment
python -m venv venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\venv\Scripts\Activate.ps1

# You should now see (venv) at the start of your prompt.

# 4. Install dependencies
pip install -r requirements.txt

# 5. Set up the database
python manage.py migrate
python manage.py seed_services      # adds Photocopying, Printing, etc.
python manage.py createsuperuser    # create your admin login

# 6. Run the app
python manage.py runserver
```

Then open **http://127.0.0.1:8000/** in your browser and log in with the
admin account you just created.

## Everyday use

Each time you want to run it again, from inside the `nebissi` folder:

```powershell
.\venv\Scripts\Activate.ps1
python manage.py runserver
```

Stop the server with `Ctrl+C`.

## Adding more admins

```powershell
python manage.py createsuperuser
```

Every admin account can see and manage all payments — there's no per-admin
restriction, since this is meant for the shop's staff to share one ledger.

## Where your data lives

Everything is stored in `db.sqlite3` in this folder. Back that file up
(copy it somewhere safe) if you want to keep records long-term or move the
app to another computer.

## Deploying so it's reachable from other devices on the network

By default the server only listens on your own computer
(`127.0.0.1`). To let other computers on the same network reach it (e.g. a
front-desk PC), run:

```powershell
python manage.py runserver 0.0.0.0:8000
```

Then on another device on the same network, visit
`http://<this-computer's-IP-address>:8000/`. This is still meant for local/
trusted networks — the built-in server (`runserver`) says explicitly it
isn't meant for production/internet-facing use. For that you'd want a real
deployment (e.g. gunicorn + nginx, or a host like Render/Railway) — ask if
you'd like help setting that up later.
