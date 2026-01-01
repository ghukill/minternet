#!/usr/bin/env python3
"""Generate minternet index.html with links to all domains."""
import json
import os
from pathlib import Path


def main() -> None:
    strategy = os.environ.get("MINTERNET_STRATEGY", "local")

    domains_dir = Path(__file__).parent.parent / "domains"
    minternet_site = domains_dir / "minternet" / "site"

    links = []
    for domain_json in sorted(domains_dir.glob("*/domain.json")):
        if domain_json.parent.name == "minternet":
            continue
        with open(domain_json) as f:
            config = json.load(f)

        name = config["name"]
        if strategy == "local":
            env = config.get("local_env", {})
            scheme = env.get("PUBLIC_SCHEME", "http")
            host = env.get("PUBLIC_HOST", f"{name}.test")
        else:
            env = config.get("env", {})
            scheme = env.get("PUBLIC_SCHEME", "https")
            host = env.get("PUBLIC_HOST", f"{config['domain']}.exe.xyz")

        url = f"{scheme}://{host}"
        links.append(f'        <li><a href="{url}">{name}</a></li>')

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>The Minternet</title>
</head>
<body>
    <h1>The Minternet</h1>
    <ul>
{chr(10).join(links)}
    </ul>
</body>
</html>
"""

    output_path = minternet_site / "index.html"
    output_path.write_text(html)
    print(f"Generated {output_path} for strategy: {strategy}")


if __name__ == "__main__":
    main()
