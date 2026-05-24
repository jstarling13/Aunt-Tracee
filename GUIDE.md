# YOUR SALES SYNC SYSTEM — Simple Guide

**Written for: [Aunt's Name]**

---

## What does this system do?

Every night, this program automatically takes your daily sales numbers from **Crunchtime** (the system your restaurant uses to track sales) and sends them to **QuickBooks** (your accounting software).

You do not need to do anything for the normal daily sync. It runs automatically at 11 PM every night.

This guide tells you how to check that it is working, and what to do if something goes wrong.

---

## How to check if today's sync worked

1. Open a web browser (Chrome, Edge, or Firefox)
2. Type this in the address bar and press Enter:
   ```
   http://localhost:5000
   ```
3. You will see the **Sales Sync Dashboard**

On the dashboard, look at the top-left box labeled **"Today's Sync"**:

| What it says | What it means |
|---|---|
| **DONE** (green) | ✓ Everything worked. No action needed. |
| **Not yet** (yellow) | The sync hasn't run yet today. Check again after 11 PM. |
| **FAILED** (red) | Something went wrong. See "What to do if you get a failure" below. |

---

## What to do if you get a failure email

You will receive an email with the subject **"[Crunchtime Sync] Sync FAILED"** if something goes wrong.

**Step 1:** Don't panic. The system will automatically try again at 11:30 PM.

**Step 2:** Open the dashboard (http://localhost:5000) and look at the red **"Failed"** count in the top cards.

**Step 3:** If it is still failing the next morning, contact:

> **[YOUR NAME]**
> Phone: [YOUR PHONE]
> Email: [YOUR EMAIL]

---

## How to manually trigger a sync

If you want to run the sync right now instead of waiting for 11 PM:

1. Open the dashboard: http://localhost:5000
2. Click the blue button that says **"▶ Run Sync Now"**
3. Wait a few seconds and the page will update
4. If it says the sync was queued, it is working

---

## What NOT to touch

Please do not change these things unless your nephew told you to:

- Do not edit the file called **config.py**
- Do not close the black terminal windows that say "SOAP server listening"
- Do not stop the ngrok program
- Do not uninstall QuickBooks Web Connector
- Do not change any settings in QuickBooks Web Connector

If you accidentally close a terminal window, contact your nephew so he can walk you through restarting it.

---

## How to restart the system (if the computer was restarted)

If the computer was turned off or restarted, you need to start two programs again:

**Step 1 — Start ngrok:**
- Find the terminal shortcut your nephew left on the desktop
- Double-click it to open a black terminal window
- Type: `ngrok http 8000` and press Enter
- Leave this window open

**Step 2 — Start the sync server:**
- Open another terminal window
- Type: `python main.py serve` and press Enter
- Leave this window open

**Step 3 — Check the dashboard** at http://localhost:5000 to confirm everything is green.

---

## What the dashboard shows you

| Section | What it means |
|---|---|
| **Today's Sync** | Did today's sales data go through? |
| **Last Synced** | The last time a sync worked successfully |
| **Total Syncs** | How many syncs have happened in total |
| **Failed** | How many syncs need attention |
| **Bar chart** | Your daily gross sales over the last 30 days |
| **Sync History table** | A detailed list of every sync — green = good, red = problem |

---

## Glossary (plain English)

| Word | What it means |
|---|---|
| **Sync** | Sending your sales data from Crunchtime to QuickBooks |
| **Crunchtime** | The program that tracks your restaurant's sales |
| **QuickBooks** | Your accounting software |
| **Dashboard** | The website at http://localhost:5000 that shows the system's status |
| **SOAP server** | A background program that connects everything together (leave it running) |
| **ngrok** | A program that lets QuickBooks communicate with the sync system |

---

## Who to call

If something is broken and you cannot fix it using the steps above:

> **[YOUR NAME]**
> Phone: [YOUR PHONE]
> Email: [YOUR EMAIL]

Please take a screenshot of the dashboard and any error messages before calling — it will help diagnose the problem faster.

---

*This guide was written for you. If anything is confusing, just call.*
