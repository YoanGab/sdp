import json
import os
import sys


def main() -> None:
    size: str = sys.argv[1]
    solutions: dict = {}
    folder_path: str = f"solutions/{size}"
    for file in sorted(
        [f for f in os.listdir(folder_path) if f.split(".")[0].isdigit()],
        key=lambda x: int(x.split(".")[0]),
        reverse=True,
    ):
        file_path: str = f"{folder_path}/{file}"
        day: int = int(file.split(".")[0])
        with open(file_path, "r") as f:
            solutions[day] = json.load(f)

    with open(f"{folder_path}/solutions.json", "w") as f:
        json.dump(solutions, f)


if __name__ == "__main__":
    main()
