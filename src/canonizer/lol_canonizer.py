"""
League of Legends データ正規化モジュール

Riot Timeline JSON を共通イベントスキーマに変換する
"""

from typing import Dict, Any, List
from .event import Event


class LoLCanonizer:
    """Convert Riot Timeline JSON -> List[Event]"""

    @staticmethod
    def timeline_to_events(tl: Dict[str, Any]) -> List[Event]:
        events: List[Event] = []
        for frame in tl.get("info", {}).get("frames", []):
            ts_base = frame["timestamp"] / 1000.0  # ms -> s
            for e in frame.get("events", []):
                etype = e.get("type")
                event_timestamp = e.get("timestamp", frame["timestamp"]) / 1000.0
                
                if etype == "CHAMPION_KILL":
                    events.append(Event(
                        timestamp=event_timestamp,
                        event="kill",
                        actor=str(e["killerId"]),
                        target=str(e["victimId"]),
                        meta={
                            "assists": e.get("assistingParticipantIds", []),
                            "position": e.get("position")
                        }
                    ))
                
                elif etype == "SKILL_LEVEL_UP":
                    events.append(Event(
                        timestamp=event_timestamp,
                        event="skill_levelup",
                        actor=str(e["participantId"]),
                        target=None,
                        meta={
                            "skillSlot": e.get("skillSlot"),
                            "levelUpType": e.get("levelUpType")
                        }
                    ))
                
                elif etype == "ITEM_PURCHASED":
                    events.append(Event(
                        timestamp=event_timestamp,
                        event="item_buy",
                        actor=str(e["participantId"]),
                        target=None,
                        meta={
                            "itemId": e.get("itemId")
                        }
                    ))
                
                elif etype == "ITEM_SOLD":
                    events.append(Event(
                        timestamp=event_timestamp,
                        event="item_sell",
                        actor=str(e["participantId"]),
                        target=None,
                        meta={
                            "itemId": e.get("itemId")
                        }
                    ))
                
                elif etype == "WARD_PLACED":
                    events.append(Event(
                        timestamp=event_timestamp,
                        event="ward_place",
                        actor=str(e["creatorId"]),
                        target=None,
                        meta={
                            "wardType": e.get("wardType"),
                            "position": e.get("position")
                        }
                    ))
                
                elif etype == "WARD_KILL":
                    events.append(Event(
                        timestamp=event_timestamp,
                        event="ward_destroy",
                        actor=str(e["killerId"]),
                        target=None,
                        meta={
                            "wardType": e.get("wardType"),
                            "position": e.get("position")
                        }
                    ))
                
                elif etype == "BUILDING_KILL":
                    events.append(Event(
                        timestamp=event_timestamp,
                        event="objective_destroy",
                        actor=str(e["killerId"]),
                        target=None,
                        meta={
                            "buildingType": e.get("buildingType"),
                            "teamId": e.get("teamId"),
                            "position": e.get("position")
                        }
                    ))
                
                elif etype == "MONSTER_KILL":
                    events.append(Event(
                        timestamp=event_timestamp,
                        event="monster_kill",
                        actor=str(e["killerId"]),
                        target=None,
                        meta={
                            "monsterType": e.get("monsterType"),
                            "monsterSubType": e.get("monsterSubType"),
                            "position": e.get("position")
                        }
                    ))
                    
        return events