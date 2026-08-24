import argparse
from tara.orchestrator import TARAOrchestrator


def parse_args():
    parser = argparse.ArgumentParser(description="TARA: Transformative AI Reasoning Architecture")
    parser.add_argument(
        "--mode",
        choices=["text", "voice", "wake"],
        default="text",
        help="Interaction mode: text (CLI chat), voice (manual push-to-talk), or wake (hands-free 'Hey TARA')"
    )
    parser.add_argument("--voice-output", action="store_true", default=False, help="Enable TTS voice playback in text mode")
    return parser.parse_args()


def main():
    args = parse_args()
    orchestrator = TARAOrchestrator(mode=args.mode, voice_output=args.voice_output)
    orchestrator.run()


if __name__ == "__main__":
    main()
