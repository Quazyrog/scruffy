import csv
import difflib
from typing import Optional, Tuple

import discord

FIELDS_NAMES = ["FirstName", "LastName", "Group", "DiscordId"]
FIRST_NAME_MATCH_RATIO_THRESHOLD = 0.50
LAST_NAME_MATCH_RATIO_THRESHOLD = 0.90


class NickInUseError(ValueError):
    pass


class Journal:
    def __init__(self):
        self._indexed_names = {}
        self._indexed_ids = {}
        self._data = []

    def read(self, csv_path: str) -> None:
        with open(csv_path) as stream:
            reader = csv.DictReader(stream)
            for member in reader:
                name = (member["LastName"], member["FirstName"])
                if member["DiscordId"]:
                    member["DiscordId"] = int(member["DiscordId"])
                if name in self._indexed_names:
                    raise ValueError(f"Name {name} appears twice in journal file")
                if member["DiscordId"] and member["DiscordId"] in self._indexed_ids:
                    raise ValueError(f"Nick {member['DiscordId']} appears twice in journal file")
                self._indexed_names[name] = len(self._data)
                if member["DiscordId"]:
                    self._indexed_ids[member["DiscordId"]] = len(self._data)
                self._data.append(member)

    def save(self, csv_path: str) -> None:
        with open(csv_path, "w") as stream:
            writer = csv.DictWriter(stream, FIELDS_NAMES, extrasaction="ignore")
            writer.writeheader()
            for member in self._data:
                writer.writerow(member)

    def match_name(self, first_name: str, last_name: str, discord_id: int) -> Optional[str]:
        name = (last_name, first_name)
        if name not in self._indexed_names:
            return None
        if discord_id in self._indexed_ids:
            raise NickInUseError(f"Member with id {discord_id} requested to authorize twice")
        idx = self._indexed_names[name]
        self._indexed_ids[discord_id] = idx
        member = self._data[idx]
        assert member["FirstName"] == first_name
        assert member["LastName"] == last_name
        assert not member["DiscordId"]
        member["DiscordId"] = discord_id
        return member["Group"]

    def match_name_weak(self, first_name: str, last_name: str, discord_id: int) -> Optional[str]:
        if result := self.match_name(first_name, last_name, discord_id):
            return result
        first_name_matcher = difflib.SequenceMatcher(autojunk=False)
        first_name_matcher.set_seq2(first_name)
        last_name_matcher = difflib.SequenceMatcher(autojunk=False)
        last_name_matcher.set_seq2(last_name)
        for member in self._data:
            last_name_matcher.set_seq1(member["LastName"])
            if last_name_matcher.ratio() < LAST_NAME_MATCH_RATIO_THRESHOLD:
                continue
            first_name_matcher.set_seq1(member["FirstName"])
            if first_name_matcher.ratio() >= FIRST_NAME_MATCH_RATIO_THRESHOLD:
                break
        else:
            return None
        return self.match_name(member["FirstName"], member["LastName"], discord_id)

    def is_introduced(self, user):
        return user.id in self._indexed_ids

    def name_of(self, user: discord.User) -> Optional[Tuple[str, str]]:
        if user.id in self._indexed_ids:
            data = self._data[self._indexed_ids[user.id]]
            return data["FirstName"], data["LastName"]
        return None
