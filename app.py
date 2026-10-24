
from flask import Flask, render_template, request
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from datetime import date, timedelta
import hashlib
import ipaddress
import socket
import random
import os

app = Flask(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; WebsiteInspector/1.0)"
}


def validate_url(raw_url):
    raw_url = raw_url.strip()

    if not raw_url:
        raise ValueError("Please enter a website URL.")

    if "://" not in raw_url:
        raw_url = "https://" + raw_url

    parsed = urlparse(raw_url)

    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only HTTP and HTTPS websites are supported.")

    if not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Please enter a valid public website URL.")

    if parsed.port not in (None, 80, 443):
        raise ValueError("Custom ports are not supported.")

    host = parsed.hostname.lower().rstrip(".")

    if host == "localhost" or host.endswith(".localhost"):
        raise ValueError("Local websites are not supported.")

    try:
        addresses = socket.getaddrinfo(host, None)
        for address in addresses:
            ip = ipaddress.ip_address(address[4][0])
            if not ip.is_global:
                raise ValueError("Please enter a publicly accessible website.")
    except ValueError:
        raise
    except (socket.gaierror, OSError):
        raise ValueError("The domain could not be found. Check the URL.")

    return raw_url


def inspect_website(raw_url):
    safe_url = validate_url(raw_url)

    try:
        response = requests.get(
            safe_url,
            headers=HEADERS,
            timeout=8,
            allow_redirects=False,
            stream=True
        )
    except requests.RequestException:
        raise ValueError(
            "Could not connect to this website. Check the URL and try again."
        )

    try:
        if 300 <= response.status_code < 400:
            raise ValueError(
                "This website redirects to another address. "
                "Try entering its final HTTPS address."
            )

        content_type = response.headers.get("Content-Type", "").lower()

        if "text/html" not in content_type:
            raise ValueError("This address did not return an HTML webpage.")

        chunks = []
        size = 0

        for chunk in response.iter_content(chunk_size=16384):
            if not chunk:
                continue
            size += len(chunk)
            if size > 1_000_000:
                break
            chunks.append(chunk)

        html = b"".join(chunks).decode(
            response.encoding or "utf-8",
            errors="replace"
        )

        status_code = response.status_code
        final_url = safe_url
    finally:
        response.close()

    soup = BeautifulSoup(html, "html.parser")
    parsed = urlparse(final_url)

    title_tag = soup.find("title")
    title = (
        title_tag.get_text(" ", strip=True)
        if title_tag else "Title not available"
    )

    description_tag = soup.find(
        "meta", attrs={"name": "description"}
    )
    description = (
        description_tag.get("content", "").strip()
        if description_tag else "Description not available."
    )

    links = []
    seen = set()

    for tag in soup.find_all("a", href=True):
        link_url = urljoin(final_url, tag["href"])
        link_parsed = urlparse(link_url)

        if link_parsed.scheme not in ("http", "https"):
            continue

        if link_url not in seen:
            seen.add(link_url)
            links.append({
                "text": tag.get_text(" ", strip=True) or "Unnamed link",
                "url": link_url
            })

        if len(links) >= 12:
            break

    return {
        "url": final_url,
        "domain": parsed.netloc,
        "title": title,
        "description": description,
        "status": status_code,
        "links": links
    }


def make_demo_analytics(domain):
    seed = int(hashlib.sha256(domain.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)

    labels = []
    page_views = []
    unique_visitors = []
    returning_visitors = []
    records = []

    today = date.today()

    for offset in range(13, -1, -1):
        day = today - timedelta(days=offset)
        views = rng.randint(450, 1800)
        unique = int(views * rng.uniform(0.55, 0.78))
        returning = int(unique * rng.uniform(0.15, 0.35))

        labels.append(day.strftime("%d %b"))
        page_views.append(views)
        unique_visitors.append(unique)
        returning_visitors.append(returning)

        records.append({
            "date": day.strftime("%d %b %Y"),
            "page_views": views,
            "unique_visitors": unique,
            "returning_visitors": returning
        })

    total_views = sum(page_views)
    total_unique = sum(unique_visitors)
    total_returning = sum(returning_visitors)
    average_views = round(total_views / len(page_views))

    recent_average = sum(page_views[-7:]) / 7
    projection = [
        {
            "date": (today + timedelta(days=i)).strftime("%d %b"),
            "visits": max(0, round(recent_average * rng.uniform(0.9, 1.1)))
        }
        for i in range(1, 8)
    ]

    return {
        "labels": labels,
        "page_views": page_views,
        "unique_visitors": unique_visitors,
        "returning_visitors": returning_visitors,
        "total_views": total_views,
        "total_unique": total_unique,
        "total_returning": total_returning,
        "average_views": average_views,
        "records": records,
        "projection": projection
    }


@app.route("/", methods=["GET", "POST"])
def index():
    website = None
    analytics = None
    error = None
    entered_url = ""

    if request.method == "POST":
        entered_url = request.form.get("website_url", "").strip()

        try:
            website = inspect_website(entered_url)
            analytics = make_demo_analytics(website["domain"])
        except ValueError as exc:
            error = str(exc)

    return render_template(
        "index.html",
        website=website,
        analytics=analytics,
        error=error,
        entered_url=entered_url
    )

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )