"""
scripts/run_local_match.py

Run our submission/main.py against "random" or the buddy agent.
Reports statuses and rewards.

Usage:
    python scripts/run_local_match.py
    python scripts/run_local_match.py --opponent random
    python scripts/run_local_match.py --opponent buddy
"""
import sys
import os
import argparse

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def main():
    parser = argparse.ArgumentParser(description="Run a local cabt match")
    parser.add_argument(
        "--opponent", default="random",
        choices=["random", "first", "buddy"],
        help="Opponent to play against (default: random)"
    )
    parser.add_argument(
        "--debug", action="store_true", default=True,
        help="Enable debug mode (default: True)"
    )
    args = parser.parse_args()

    from kaggle_environments import make

    # Our agent
    our_agent_path = os.path.join(
        os.path.dirname(__file__), "..", "submission", "main.py"
    )
    our_agent_path = os.path.abspath(our_agent_path)

    # Opponent
    if args.opponent == "buddy":
        # The frozen bundle contains a Linux library.  The shared evaluator
        # loader imports its untouched Python policy while reusing the native
        # library already initialized by kaggle-environments for this host.
        from ptcg_agent.eval.opponents import load_opponent

        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        opponent = load_opponent("buddy", repo_root).agent
        opp_name = "buddy-lucario"
    else:
        opponent = args.opponent
        opp_name = args.opponent

    print(f"Running: our agent vs {opp_name}")
    print(f"Our agent: {our_agent_path}")

    env = make("cabt", debug=args.debug)
    env.run([our_agent_path, opponent])
    js = env.toJSON()

    print(f"Statuses: {js['statuses']}")
    print(f"Rewards:  {js['rewards']}")

    # Check for issues
    for i, status in enumerate(js["statuses"]):
        if status == "INVALID":
            print(f"  [WARN] Player {i} INVALID")
        elif status == "ERROR":
            print(f"  [WARN] Player {i} ERROR")
        elif status == "TIMEOUT":
            print(f"  [WARN] Player {i} TIMEOUT")

    if js["statuses"] == ["DONE", "DONE"]:
        print("[OK] Match completed successfully")
    else:
        print("[FAIL] Match did not complete cleanly")
        sys.exit(1)


if __name__ == "__main__":
    main()
