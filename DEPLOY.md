# Putting CALARO on calaro.online (free)

The whole stack (app, API, MongoDB, Grafana, Prometheus, Loki) runs on one free
Oracle Cloud server. Caddy gets the HTTPS certificate automatically. HTTPS matters
here because browsers only allow the microphone on secure sites.

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
| Server | Oracle Cloud Always Free, Ampere A1 | Since June 2026 the free allowance is 2 CPUs and 12 GB RAM (it was 4 and 24). That's comfortably enough for CALARO. Oracle asks for a card to verify you but doesn't charge for Always Free resources. |
| HTTPS certificate | Let's Encrypt via Caddy | Automatic, renews itself |
| DNS | Hostinger DNS (included with your domain) | Only the A record changes |
| Domain | calaro.online | You already have it |

Things to know about the free server:
- Pick your **home region** carefully when signing up, because it can't be changed. Mumbai or Hyderabad is closest to your users. If you see "Out of host capacity" when creating the server, try again later or try another availability domain.
- Oracle can reclaim Always Free servers that sit **idle** for a week. A live site with real traffic and the monitoring stack normally avoids this. Upgrading the account to pay-as-you-go also removes the risk, and Always Free resources stay free.

## 1. Create the server

1. Sign up at cloud.oracle.com (choose your home region).
2. **Compute → Instances → Create instance**
   - Image: **Ubuntu 24.04** (Canonical)
   - Shape: **Ampere → VM.Standard.A1.Flex**, **2 OCPU, 12 GB memory**
   - Networking: create a new VCN with a public subnet, and **assign a public IPv4 address**
   - SSH keys: upload your public key (or let Oracle generate one and **download the private key**)
   - Boot volume: 100 GB is fine (the free allowance is 200 GB in total)
3. Note the **public IP address** shown on the instance page.

## 2. Open ports 80 and 443 in Oracle's firewall

Instance page → **Subnet** → **Default Security List** → **Add Ingress Rules**:

| Source CIDR | Protocol | Destination port |
|---|---|---|
| 0.0.0.0/0 | TCP | 80 |
| 0.0.0.0/0 | TCP | 443 |
| 0.0.0.0/0 | UDP | 443 |

(The server's own firewall is opened by the setup script in step 4.)

## 3. Point calaro.online at the server (Hostinger DNS)

Your domain is registered at Hostinger. Keep it there: only the DNS records change, which is free.
Hostinger's shared web hosting can't run this app (it needs Docker), so the app runs on the Oracle server and Hostinger just points visitors to it.

1. Log in to **hPanel → Domains → calaro.online → DNS / Nameservers**.
2. Under **Nameservers**, make sure **Use Hostinger nameservers** is selected (the defaults are `ns1.dns-parking.com` / `ns2.dns-parking.com`).
3. Under **DNS records**:

| Action | Type | Name | Points to | TTL |
|---|---|---|---|---|
| **Edit** the existing record (it points at Hostinger's parking page) | A | `@` | your Oracle server's public IP | 300 |
| Keep it, or add it if missing | CNAME | `www` | `calaro.online` | 300 |
| **Delete** any record, because the Oracle server has no IPv6 address | AAAA | `@` / `www` | – | – |
| Check | CAA | `@` | If any CAA records exist, one must allow `letsencrypt.org` (add `0 issue "letsencrypt.org"`). If there are none, do nothing. | – |

4. Wait a few minutes, then check from your computer with `nslookup calaro.online`. It should show your Oracle IP.

**www.calaro.online:** to send `www.` to the main address, open `deploy/caddy/Caddyfile` on the server and replace the commented `www` block near the end with:
```
www.calaro.online {
	redir https://calaro.online{uri} permanent
}
```
Then run `docker compose restart caddy`.

## 4. Prepare the server

From your computer (PowerShell works):

```bash
ssh -i path\to\your-key ubuntu@YOUR_SERVER_IP
```

On the server:

```bash
git clone https://github.com/YOUR_GITHUB_USER/calaro.git    # see "Getting the code there" below
cd calaro
bash deploy/server-setup.sh
exit        # log out and back in so Docker works without sudo
```

**Getting the code there:** pushing the project to a **private** GitHub repository and cloning it is easiest, and `deploy/update.sh` uses it later.
Without GitHub, copy the folder from Windows instead (run this from `D:\CALARO\CALARO-main`):
`scp -i path\to\your-key -r CALARO-main ubuntu@YOUR_SERVER_IP:~/calaro`

## 5. Add your settings and secrets

On the server, in the `calaro` folder:

```bash
cp .env.example .env
nano .env
```
Set:
```
SITE_ADDRESS=calaro.online
PUBLIC_URL=https://calaro.online
ACME_EMAIL=you@example.com
```

```bash
cp backend/.env.example backend/.env
nano backend/.env
```
Set (generate the secret with `openssl rand -hex 32`):
```
SECRET_KEY=<the long random string>
SUPERADMIN_PASSWORD=<a strong password>
BHASHINI_INFERENCE_API_KEY=<your key>
BHASHINI_UDYAT_KEY=<your key>
```
If you want password-reset emails to actually send, also fill in the `SMTP_*` settings.

## 6. Start it

```bash
docker compose up --build -d
docker compose ps                 # everything should be "running"
docker compose logs -f caddy      # watch for "certificate obtained successfully", then Ctrl+C
```

Open **https://calaro.online**, sign in as `calaro@admin.calaro.com`, then go to **Admin console → Monitoring**.

The first build on the ARM server takes about 5–10 minutes.

## 7. Nightly backups

```bash
crontab -e
# add this line:
0 3 * * * /home/ubuntu/calaro/deploy/backup.sh >> /home/ubuntu/calaro/backups/backup.log 2>&1
```
Backups are kept on the same server, so now and then download one to your computer:
`scp -i path\to\your-key ubuntu@YOUR_SERVER_IP:~/calaro/backups/<file> .`

## Updating later

```bash
cd ~/calaro && bash deploy/update.sh
```

## What the Monitoring tab shows

| View | Shows |
|---|---|
| Traffic & usage | Requests per minute (whole site and API), error rate, API speed (p50/p95/p99), slowest and busiest endpoints, sign-ins (including failed ones), people active today/this week/this month, meals per language, how often foods were understood, voice vs typed, member goals, Bhashini response time |
| Logs | Every container's logs, searchable and filterable by service, warnings and errors, slow API calls, the most visited pages, and unique visitors. Kept for 14 days. |
| Server health | CPU, memory, disk, network, the API process, and which services are up |

Only CALARO admins can open it. The super-admin is a Grafana admin, and other admins can view only.

## If something goes wrong

| Symptom | Fix |
|---|---|
| Browser can't reach the site | Check ports 80/443 in step 2, run `sudo iptables -L INPUT -n` on the server, and confirm DNS with `nslookup calaro.online` |
| Caddy log says certificate failed | DNS isn't pointing at the server yet, port 80 is blocked, or an AAAA or CAA record at Hostinger is in the way (step 3). Fix it, then `docker compose restart caddy` |
| Microphone doesn't work | The site must be opened over **https://** |
| Monitoring tab is blank | `docker compose ps grafana` and `docker compose logs grafana` |
| Lost the super-admin password | Use "Forgot password" on the sign-in page (needs SMTP), or ask for help resetting it in the database |
