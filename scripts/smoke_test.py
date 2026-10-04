"""Smoke test: random vs first on cabt."""
from kaggle_environments import make

print("Creating cabt environment...")
env = make("cabt", debug=True)

print("Running random vs first...")
env.run(["random", "first"])
js = env.toJSON()

print(f"statuses = {js['statuses']}")
print(f"rewards  = {js['rewards']}")

assert js["statuses"] == ["DONE", "DONE"], f"FAIL: {js['statuses']}"
assert sorted(js["rewards"]) in ([-1, 1], [0, 0]), f"FAIL: {js['rewards']}"

print("SMOKE TEST PASSED")
