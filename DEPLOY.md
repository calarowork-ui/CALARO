# Putting CALARO on calaro.online (free, no credit card)

The whole stack (app, API, MongoDB, Grafana, Prometheus and Loki) runs on one small free server from
**Azure for Students**. Caddy gets the HTTPS certificate automatically. HTTPS matters because browsers
only allow the microphone on secure sites.

```
calaro.online ──► Caddy (HTTPS) ─┬─ /            React app
                                 ├─ /api/*       FastAPI ── MongoDB
                                 └─ /grafana/*   Grafana (admins only, checked by the API on every request)
           Prometheus ◄── metrics from the API, Caddy and the server
           Loki       ◄── Alloy ◄── logs from every container
```

## What it costs

| Piece | Free option | Notes |
|---|---|---|
| Server | Azure for Students, **B2ats v2** VM (2 vCPU, 1 GB RAM) | Sign up with your college email. No card needed. 750 free VM hours a month for 12 months, plus $100 credit. You can renew each year while you're a student. |
| Public IP and disk | Paid from the $100 credit | Roughly $3–4 a month for the IP. Azure for Students has a spending limit, so you are **never billed**. If the credit ever runs out, the server just pauses. |
| HTTPS certificate | Let's Encrypt via Caddy | Automatic, and it renews itself |
| DNS | Hostinger DNS (included with your domain) | Only the A record changes |
| Code | Private GitHub repo | Auto-deploys after the tests pass |

1 GB of memory is small, so the server runs with `docker-compose.small.yml`, which caps each service's
memory, plus 4 GB of swap. That's plenty for a new app's traffic.

## 1. Get Azure for Students

1. Open **azure.microsoft.com/free/students** and choose **Start free**.
2. Sign in with a Microsoft account. Verify with your **college email** (or the other student check it offers).
3. When it finishes, you land in the Azure portal (portal.azure.com) with an **Azure for Students** subscription.

## 2. Create the server

In the portal, search for **Free services**, find **Virtual machines (Linux)** and click **Create**.
Creating it from that page makes sure the free size is picked.

**Basics tab**

| Setting | Value |
|---|---|
| Resource group | Create new: `calaro` |
| Virtual machine name | `calaro` |
| Region | **(Asia Pacific) Central India**. If it says the region isn't allowed for your subscription, try South India or Southeast Asia. |
| Availability options | No infrastructure redundancy required |
| Security type | Standard |
| Image | **Ubuntu Server 24.04 LTS – x64 Gen2** |
| Size | **Standard_B2ats_v2** (2 vCPU, 1 GiB). It's labelled *Free services eligible*. B1s is the fallback. |
| Authentication | SSH public key, username **`azureuser`**, *Generate new key pair*, key name `calaro_key` |
| Inbound ports | Allow **SSH (22), HTTP (80), HTTPS (443)** |

**Disks tab:** OS disk size **64 GiB**, type **Premium SSD**. This matches the free P6 disk.

**Networking tab:** keep the new public IP and tick **Delete public IP and NIC when VM is deleted**.

**Management tab:** make sure **Auto-shutdown is off**.

Click **Review + create** and then **Create**. When asked, click **Download private key and create resource**,
and keep `calaro_key.pem` safe. When it's done, open the VM and note its **Public IP address**.

Optional (HTTP/3): VM → **Networking → Add inbound port rule** with destination port 443, protocol **UDP**, named `https-udp`.

## 3. Connect to the server

From PowerShell on your computer:

```powershell
icacls $HOME\Downloads\calaro_key.pem /inheritance:r /grant:r "$($env:USERNAME):R"
ssh -i $HOME\Downloads\calaro_key.pem azureuser@YOUR_SERVER_IP
```
The first line fixes the "unprotected private key file" error that Windows can cause.

## 4. Get the code onto the server (private repo)

On the server, make a read-only key that only works for your repo:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/github_read -N ""
printf "Host github.com\n  IdentityFile ~/.ssh/github_read\n" >> ~/.ssh/config
cat ~/.ssh/github_read.pub
```
On GitHub, open **calarowork-ui/CALARO → Settings → Deploy keys → Add deploy key**. Paste the line,
name it `azure-server`, and leave *Allow write access* **off**.

Then, on the server:

```bash
git clone git@github.com:calarowork-ui/CALARO.git calaro    # type "yes" to trust github.com
cd calaro
bash deploy/server-setup.sh     # installs Docker, adds 4 GB swap, turns on security updates
exit                            # log out and back in so Docker works without sudo
```

## 5. Add your settings and secrets

Connect again (step 3), then:

```bash
cd ~/calaro
cp .env.example .env
nano .env
```
Set these lines (remove the `localhost` ones):
```
SITE_ADDRESS=calaro.online
PUBLIC_URL=https://calaro.online
ACME_EMAIL=calaro.work@gmail.com
COMPOSE_FILE=docker-compose.yml:docker-compose.small.yml
```
`COMPOSE_FILE` switches on the 1 GB settings. Every `docker compose` command and every auto-deploy uses them automatically.

```bash
cp backend/.env.example backend/.env
openssl rand -hex 32            # copy the output for SECRET_KEY
nano backend/.env
```
Set:
```
SECRET_KEY=<the long random string>
SUPERADMIN_PASSWORD=<a strong password>
ACCESS_TOKEN_EXPIRE_MINUTES=720
BHASHINI_INFERENCE_API_KEY=<your key>
BHASHINI_UDYAT_KEY=<your key>
```
To save in nano, press Ctrl+O, Enter, then Ctrl+X. If you want password-reset emails to actually send, also fill in the `SMTP_*` settings.

## 6. Point calaro.online at the server (Hostinger)

Your site is currently on GitHub Pages, so you'll swap its records for the Azure server.

**hPanel → Domains → calaro.online → DNS / Nameservers → DNS records**:

| Action | Type | Name | Points to | TTL |
|---|---|---|---|---|
| **Delete** all four GitHub Pages records (`185.199.108.153`, `.109.153`, `.110.153`, `.111.153`) | A | `@` | – | – |
| **Add** | A | `@` | your Azure server's public IP | 300 |
| **Edit** (it probably points to `yourname.github.io`) | CNAME | `www` | `calaro.online` | 300 |
| **Delete** any (GitHub Pages IPv6) | AAAA | `@` / `www` | – | – |
| Check | CAA | `@` | If any CAA records exist, one must allow `letsencrypt.org`. If there are none, do nothing. | – |

Wait 5–10 minutes. Then, on your computer, run `nslookup calaro.online`. It should show the Azure IP.

## 7. Start it

On the server:

```bash
cd ~/calaro
docker compose up --build -d      # the first build takes 10–20 minutes on this small server
docker compose ps                 # everything should be "running"
docker compose logs -f caddy      # wait for "certificate obtained successfully", then Ctrl+C
```

Open **https://calaro.online**, sign in as `calaro@admin.calaro.com` with your `SUPERADMIN_PASSWORD`,
then go to **Admin console → Monitoring**.

Then switch off the old site. In **your old GitHub Pages repo → Settings → Pages**, unpublish it or set Source
to *None*, and delete any `CNAME` file there. This stops GitHub from claiming calaro.online.

**www.calaro.online:** to send `www.` to the main address, run `nano deploy/caddy/Caddyfile` and replace the commented
`www` block near the end with:
```
www.calaro.online {
	redir https://calaro.online{uri} permanent
}
```
Then run `docker compose restart caddy`.

## 8. Auto-deploy from GitHub

On the server, make a key that GitHub Actions uses to log in:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/github_actions -N ""
cat ~/.ssh/github_actions.pub >> ~/.ssh/authorized_keys
cat ~/.ssh/github_actions          # the PRIVATE key; copy all of it, including the BEGIN/END lines
```
On GitHub, open **CALARO → Settings → Secrets and variables → Actions → New repository secret** and add three secrets:

| Name | Value |
|---|---|
| `SSH_HOST` | the server's public IP |
| `SSH_USER` | `azureuser` |
| `SSH_KEY` | the private key you just copied |

From now on, every push to `main` runs the tests, and if they pass, the server updates itself.
You can also run it by hand from **Actions → Deploy → Run workflow**.

## 9. Nightly backups

```bash
mkdir -p ~/calaro/backups
crontab -e
# add this line:
0 3 * * * $HOME/calaro/deploy/backup.sh >> $HOME/calaro/backups/backup.log 2>&1
```
Backups stay on the same server, so now and then download one to your computer:
`scp -i $HOME\Downloads\calaro_key.pem azureuser@YOUR_SERVER_IP:~/calaro/backups/<file> .`

## Updating by hand

```bash
cd ~/calaro && bash deploy/update.sh
```

## Keeping an eye on the free allowance

- In the portal, check **Cost Management → Cost analysis** once a month. Charges should only be the IP, and they come out of the credit.
- Run just **one** VM. 750 free hours covers one server running all month.
- **Don't** resize the VM, add more disks, or create a second public IP.
- Azure emails you before the 12 months end. Renew Azure for Students then.

## What the Monitoring tab shows

| View | Shows |
|---|---|
| Traffic & usage | Requests per minute, error rate, API speed (p50/p95/p99), slowest and busiest endpoints, sign-ins (including failed ones), active people, meals per language, voice vs typed, member goals, Bhashini response time |
| Logs | Every container's logs, searchable by service. Warnings and errors, slow API calls, top pages and unique visitors. Kept for 14 days. |
| Server health | CPU, memory, disk, network, and which services are up |

Only CALARO admins can open it. The super-admin is a Grafana admin, and other admins can view only.
On the small server, metrics are kept for 15 days and logs for 14.

## If something goes wrong

| Symptom | Fix |
|---|---|
| "Region not allowed" when creating the VM | Student subscriptions only allow some regions. Try South India, Southeast Asia or East Asia. |
| `git clone` says permission denied | The deploy key isn't added on GitHub (step 4), or the `~/.ssh/config` line is missing |
| Browser can't reach the site | Check that ports 80/443 are open (VM → Networking), and confirm DNS with `nslookup calaro.online` |
| Caddy log says certificate failed | DNS isn't pointing at the server yet, or old GitHub Pages / AAAA / CAA records are in the way (step 6). Fix it, then `docker compose restart caddy` |
| Build stops with "killed" or "out of memory" | Check that swap is on with `free -h` (it should show 4 GB). Re-run `bash deploy/server-setup.sh`, then build again. |
| Site is slow | `docker stats --no-stream` shows memory per service. If `free -h` shows swap heavily used all the time, the server is too small for the traffic. |
| Microphone doesn't work | The site must be opened over **https://** |
| Monitoring tab is blank | `docker compose ps grafana` and `docker compose logs grafana` |

## Other servers

The same steps work on any Ubuntu server with Docker. On a server with 4 GB or more (for example Oracle Cloud
Always Free, if you get a card later), leave out the `COMPOSE_FILE` line so the services can use more memory.
On Oracle, also open ports 80/443 in the subnet's security list, and use `ubuntu` as the user name.
