import argparse
import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError

load_dotenv()

STATE_FILE = Path("instance/telegram_auth_state.json")
ENV_FILE = Path(".env")


def _get_api_credentials() -> tuple[int, str, str]:
    api_id = int(os.getenv("TELEGRAM_API_ID", "0") or "0")
    api_hash = os.getenv("TELEGRAM_API_HASH", "")
    phone = os.getenv("TELEGRAM_PHONE", "")

    if not api_id or not api_hash or not phone:
        raise RuntimeError("TELEGRAM_API_ID/TELEGRAM_API_HASH/TELEGRAM_PHONE must be set in .env")

    return api_id, api_hash, phone


def _ensure_instance_dir() -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)


def _save_state(state: dict) -> None:
    _ensure_instance_dir()
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_state() -> dict:
    if not STATE_FILE.exists():
        raise RuntimeError("Auth state not found. Run request step first.")
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def _update_env_session(new_session: str) -> None:
    if not ENV_FILE.exists():
        raise RuntimeError(".env file not found")

    lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
    updated = False

    for idx, line in enumerate(lines):
        if line.startswith("TELEGRAM_SESSION_STRING="):
            lines[idx] = f"TELEGRAM_SESSION_STRING={new_session}"
            updated = True
            break

    if not updated:
        lines.append(f"TELEGRAM_SESSION_STRING={new_session}")

    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def request_code() -> None:
    api_id, api_hash, phone = _get_api_credentials()

    client = TelegramClient(StringSession(""), api_id, api_hash)
    await client.connect()
    try:
        sent = await client.send_code_request(phone)
        state = {
            "phone": phone,
            "phone_code_hash": sent.phone_code_hash,
            "session_string": client.session.save(),
        }
        _save_state(state)
        print("SMS code requested successfully.")
        print("State saved to instance/telegram_auth_state.json")
    finally:
        await client.disconnect()


async def verify_code(code: str, password: str | None) -> None:
    api_id, api_hash, _phone_from_env = _get_api_credentials()
    state = _load_state()

    phone = state["phone"]
    phone_code_hash = state["phone_code_hash"]
    login_session = state["session_string"]

    client = TelegramClient(StringSession(login_session), api_id, api_hash)

    await client.connect()
    try:
        try:
            await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
        except SessionPasswordNeededError:
            if not password:
                raise RuntimeError("2FA password required. Re-run verify with --password")
            await client.sign_in(password=password)

        if not await client.is_user_authorized():
            raise RuntimeError("Authorization failed. Please try request again.")

        new_session = client.session.save()
    finally:
        await client.disconnect()

    _update_env_session(new_session)

    try:
        STATE_FILE.unlink(missing_ok=True)
    except Exception:
        pass

    print("Session authorized successfully.")
    print("Updated TELEGRAM_SESSION_STRING in .env")


def main() -> None:
    parser = argparse.ArgumentParser(description="Telegram session auth helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("request", help="Request SMS code and save auth state")

    verify_parser = subparsers.add_parser("verify", help="Verify SMS code and update .env session")
    verify_parser.add_argument("--code", required=True, help="SMS code from Telegram")
    verify_parser.add_argument("--password", required=False, help="2FA password if enabled")

    args = parser.parse_args()

    if args.command == "request":
        asyncio.run(request_code())
    elif args.command == "verify":
        asyncio.run(verify_code(args.code, args.password))


if __name__ == "__main__":
    main()
