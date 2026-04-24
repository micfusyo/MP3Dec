import shutil
import plistlib
import subprocess
import tempfile
import textwrap
import zlib
from pathlib import Path
from struct import pack
from typing import Optional, Tuple


APP_NAME = "MP3BatchConverter"
ROOT_DIR = Path(__file__).resolve().parent
DIST_DIR = ROOT_DIR / "dist"
APP_BUNDLE = DIST_DIR / f"{APP_NAME}.app"
FINAL_DMG = DIST_DIR / f"{APP_NAME}.dmg"


def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    return pack(">I", len(data)) + chunk_type + data + pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)


def write_background_png(path: Path, width: int = 640, height: int = 360) -> None:
    rows = []
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            top_mix = y / max(height - 1, 1)
            left_mix = x / max(width - 1, 1)
            red = int(247 - 22 * top_mix - 10 * left_mix)
            green = int(242 - 18 * top_mix)
            blue = int(231 - 12 * top_mix + 8 * left_mix)

            if 32 < x < 310 and 36 < y < 324:
                red = min(255, red + 6)
                green = min(255, green + 6)
                blue = min(255, blue + 8)

            if 330 < x < 608 and 36 < y < 324:
                red = max(0, red - 8)
                green = max(0, green - 8)
                blue = max(0, blue - 6)

            if 312 <= x <= 328 and 100 < y < 258:
                red = 214
                green = 106
                blue = 72

            row.extend((red, green, blue))
        rows.append(bytes(row))

    png_data = b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            png_chunk(b"IHDR", pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)),
            png_chunk(b"IDAT", zlib.compress(b"".join(rows), level=9)),
            png_chunk(b"IEND", b""),
        ]
    )
    path.write_bytes(png_data)


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, text=True, **kwargs)


def configure_finder_window(volume_name: str) -> None:
    script = textwrap.dedent(
        f"""
        tell application "Finder"
            tell disk "{volume_name}"
                open
                tell container window
                    set current view to icon view
                    set toolbar visible to false
                    set statusbar visible to false
                    set bounds to {{120, 120, 760, 480}}
                end tell
                set theViewOptions to the icon view options of container window
                set arrangement of theViewOptions to not arranged
                set icon size of theViewOptions to 100
                set text size of theViewOptions to 14
                set background picture of theViewOptions to file ".background:background.png"
                set position of item "{APP_NAME}.app" of container window to {{180, 210}}
                set position of item "Applications" of container window to {{470, 210}}
                update without registering applications
                delay 2
                close
                open
                delay 1
            end tell
        end tell
        """
    ).strip()
    run(["osascript", "-e", script])


def attach_image(dmg_path: Path) -> Tuple[str, Path]:
    completed = run(
        [
            "hdiutil",
            "attach",
            str(dmg_path),
            "-noverify",
            "-noautoopen",
            "-plist",
        ],
        capture_output=True,
    )
    data = plistlib.loads(completed.stdout.encode("utf-8"))
    device = ""
    mount_point: Optional[Path] = None

    for entity in data.get("system-entities", []):
        if not device and entity.get("dev-entry"):
            device = entity["dev-entry"]
        if entity.get("mount-point"):
            mount_point = Path(entity["mount-point"])

    if not device or mount_point is None:
        raise RuntimeError("無法解析 DMG 掛載資訊。")

    return device, mount_point


def main() -> None:
    if not APP_BUNDLE.exists():
        raise SystemExit(f"找不到 App bundle：{APP_BUNDLE}")

    with tempfile.TemporaryDirectory(prefix="mp3batch_dmg_") as temp_dir:
        temp_path = Path(temp_dir)
        staging_dir = temp_path / "staging"
        background_dir = staging_dir / ".background"
        rw_dmg = temp_path / f"{APP_NAME}_temp.dmg"

        background_dir.mkdir(parents=True)

        shutil.copytree(APP_BUNDLE, staging_dir / APP_BUNDLE.name, symlinks=True)
        (staging_dir / "Applications").symlink_to("/Applications")
        write_background_png(background_dir / "background.png")

        run(
            [
                "hdiutil",
                "create",
                "-volname",
                APP_NAME,
                "-srcfolder",
                str(staging_dir),
                "-fs",
                "HFS+",
                "-fsargs",
                "-c c=64,a=16,e=16",
                "-format",
                "UDRW",
                "-ov",
                str(rw_dmg),
            ]
        )

        device, mount_dir = attach_image(rw_dmg)

        try:
            hidden_background = mount_dir / ".background"
            hidden_background.mkdir(exist_ok=True)
            shutil.copy2(background_dir / "background.png", hidden_background / "background.png")
            configure_finder_window(mount_dir.name)
        finally:
            run(["hdiutil", "detach", device])

        if FINAL_DMG.exists():
            FINAL_DMG.unlink()

        run(
            [
                "hdiutil",
                "convert",
                str(rw_dmg),
                "-format",
                "UDZO",
                "-imagekey",
                "zlib-level=9",
                "-ov",
                "-o",
                str(FINAL_DMG),
            ]
        )

    print(FINAL_DMG)


if __name__ == "__main__":
    main()
