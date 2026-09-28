"""Group audit records by overlapping IDs/aliases; never suppress scanner findings."""

import json
import sys
from pathlib import Path


def summarize(path):
    audit = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    groups = []
    packages = {}
    for dependency in audit["dependencies"]:
        vulns = dependency.get("vulns", [])
        if vulns:
            packages[dependency["name"]] = {"version": dependency["version"], "raw_records": len(vulns)}
        for vuln in vulns:
            ids = {vuln["id"], *vuln.get("aliases", [])}
            group = {"ids": ids, "packages": {dependency["name"]}, "fixes": set(vuln.get("fix_versions", []))}
            # A record may bridge two previously separate alias groups.
            matched = [existing for existing in groups if existing["ids"] & ids]
            for existing in matched:
                for key in group:
                    group[key].update(existing[key])
                groups.remove(existing)
            groups.append(group)
    return {
        "input": str(path),
        "raw_records": sum(package["raw_records"] for package in packages.values()),
        "affected_packages": packages,
        "unique_alias_groups": len(groups),
        "advisories": [
            {key: sorted(values) for key, values in group.items()}
            for group in sorted(groups, key=lambda item: sorted(item["ids"])[0])
        ],
        "note": "Grouping is reporting only; fix versions are advisory metadata, not a compatible upgrade prescription.",
    }


if __name__ == "__main__":
    print(json.dumps(summarize(sys.argv[1]), ensure_ascii=False, indent=2))
