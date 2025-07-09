"""
VALORANT データ正規化モジュール

VALORANT マッチデータを共通イベントスキーマに変換する
"""

from typing import Dict, Any, List
from .event import Event


class ValorantCanonizer:
    """Convert VALORANT Match JSON -> List[Event]"""

    @staticmethod
    def match_to_events(match_data: Dict[str, Any], target_puuid: str = None) -> List[Event]:
        """マッチデータを共通イベントに変換"""
        events: List[Event] = []
        
        if not match_data.get("data"):
            return events
            
        data = match_data["data"]
        metadata = data.get("metadata", {})
        players = data.get("players", {}).get("all_players", [])
        rounds = data.get("rounds", [])
        
        # マッチ開始イベント
        if metadata.get("game_start"):
            events.append(Event(
                timestamp=0.0,
                event="match_start",
                actor="system",
                target=None,
                meta={
                    "map": metadata.get("map"),
                    "mode": metadata.get("mode"),
                    "game_version": metadata.get("game_version"),
                    "region": metadata.get("region")
                }
            ))
        
        # プレイヤーマッピングを作成
        player_mapping = {}
        for player in players:
            puuid = player.get("puuid")
            name = f"{player.get('name')}#{player.get('tag')}"
            agent = player.get("character")
            team = player.get("team")
            
            player_mapping[puuid] = {
                "name": name,
                "agent": agent,
                "team": team
            }
            
            # エージェント選択イベント
            events.append(Event(
                timestamp=0.0,
                event="agent_select",
                actor=name,
                target=None,
                meta={
                    "agent": agent,
                    "team": team,
                    "puuid": puuid
                }
            ))
        
        # ラウンドイベントを処理
        for round_data in rounds:
            round_num = round_data.get("round_num", 0)
            round_result = round_data.get("round_result")
            winning_team = round_data.get("winning_team")
            
            # ラウンド開始（推定タイムスタンプ）
            round_start_time = round_num * 120.0  # 2分間隔と仮定
            
            events.append(Event(
                timestamp=round_start_time,
                event="round_start",
                actor="system",
                target=None,
                meta={
                    "round_num": round_num,
                    "round_result": round_result
                }
            ))
            
            # プラント・デフューズイベント
            plant_events = round_data.get("plant_events", [])
            for plant_event in plant_events:
                plant_time = round_start_time + 30.0  # 推定
                events.append(Event(
                    timestamp=plant_time,
                    event="bomb_plant",
                    actor=plant_event.get("player_display_name", "unknown"),
                    target=None,
                    meta={
                        "round_num": round_num,
                        "plant_location": plant_event.get("plant_location"),
                        "planted_by": plant_event.get("planted_by", {})
                    }
                ))
            
            defuse_events = round_data.get("defuse_events", [])
            for defuse_event in defuse_events:
                defuse_time = round_start_time + 60.0  # 推定
                events.append(Event(
                    timestamp=defuse_time,
                    event="bomb_defuse",
                    actor=defuse_event.get("player_display_name", "unknown"),
                    target=None,
                    meta={
                        "round_num": round_num,
                        "defuse_location": defuse_event.get("defuse_location"),
                        "defused_by": defuse_event.get("defused_by", {})
                    }
                ))
            
            # プレイヤーラウンド統計
            player_stats = round_data.get("player_stats", [])
            for stat in player_stats:
                player_puuid = stat.get("player_puuid")
                player_info = player_mapping.get(player_puuid, {})
                player_name = player_info.get("name", "unknown")
                
                kills = stat.get("kills", 0)
                damage = stat.get("damage", 0)
                score = stat.get("score", 0)
                
                # キルイベント（ラウンド終了時の統計として）
                if kills > 0:
                    events.append(Event(
                        timestamp=round_start_time + 90.0,  # ラウンド終了時
                        event="round_kills",
                        actor=player_name,
                        target=None,
                        meta={
                            "round_num": round_num,
                            "kills": kills,
                            "damage": damage,
                            "score": score,
                            "puuid": player_puuid
                        }
                    ))
            
            # ラウンド終了
            events.append(Event(
                timestamp=round_start_time + 120.0,
                event="round_end",
                actor="system",
                target=None,
                meta={
                    "round_num": round_num,
                    "winning_team": winning_team,
                    "round_result": round_result
                }
            ))
        
        # マッチ終了時の最終統計
        game_length = metadata.get("game_length", 0) / 1000.0  # msを秒に変換
        
        for player in players:
            puuid = player.get("puuid")
            name = f"{player.get('name')}#{player.get('tag')}"
            stats = player.get("stats", {})
            
            events.append(Event(
                timestamp=game_length,
                event="match_performance",
                actor=name,
                target=None,
                meta={
                    "puuid": puuid,
                    "agent": player.get("character"),
                    "team": player.get("team"),
                    "kills": stats.get("kills", 0),
                    "deaths": stats.get("deaths", 0),
                    "assists": stats.get("assists", 0),
                    "score": stats.get("score", 0),
                    "headshots": stats.get("headshots", 0),
                    "bodyshots": stats.get("bodyshots", 0),
                    "legshots": stats.get("legshots", 0),
                    "damage_made": stats.get("damage", {}).get("made", 0),
                    "damage_received": stats.get("damage", {}).get("received", 0),
                    "first_bloods": stats.get("first_bloods", 0),
                    "first_deaths": stats.get("first_deaths", 0)
                }
            ))
        
        # マッチ終了イベント
        events.append(Event(
            timestamp=game_length,
            event="match_end",
            actor="system",
            target=None,
            meta={
                "match_id": metadata.get("matchid"),
                "map": metadata.get("map"),
                "rounds_played": metadata.get("rounds_played"),
                "game_length": game_length,
                "teams": data.get("teams", {})
            }
        ))
        
        return events

    @staticmethod
    def convert_round_kills_to_kill_events(events: List[Event]) -> List[Event]:
        """round_killsイベントをkillイベントに変換する"""
        kill_events = []
        
        for event in events:
            if event.event == "round_kills":
                kills_count = event.meta.get("kills", 0)
                round_num = event.meta.get("round_num", 0)
                
                # 各キルに対して個別のkillイベントを生成
                for kill_number in range(1, kills_count + 1):
                    # タイムスタンプを少しずつずらす（10秒間隔と仮定）
                    kill_timestamp = event.timestamp - 30.0 + (kill_number * 10.0)
                    
                    kill_event = Event(
                        timestamp=kill_timestamp,
                        event="kill",
                        actor=event.actor,
                        target=None,
                        meta={
                            "round_num": round_num,
                            "kill_number": kill_number,
                            "total_kills_in_round": kills_count,
                            "puuid": event.meta.get("puuid"),
                            "damage": event.meta.get("damage"),
                            "score": event.meta.get("score")
                        }
                    )
                    kill_events.append(kill_event)
        
        return kill_events

    @staticmethod
    def player_stats_to_events(stats_data: Dict[str, Any], player_name: str) -> List[Event]:
        """プレイヤー統計データを共通イベントに変換"""
        events: List[Event] = []
        
        if not stats_data.get("data"):
            return events
        
        data = stats_data["data"]
        
        # 基本統計情報
        events.append(Event(
            timestamp=0.0,
            event="player_stats",
            actor=player_name,
            target=None,
            meta={
                "puuid": data.get("puuid"),
                "region": data.get("region"),
                "account_level": data.get("account_level"),
                "card": data.get("card", {}),
                "last_update": data.get("last_update"),
                "last_update_raw": data.get("last_update_raw")
            }
        ))
        
        # 各モードの統計
        for mode_key, mode_data in data.items():
            if isinstance(mode_data, dict) and mode_key not in ["puuid", "region", "account_level", "card", "last_update", "last_update_raw"]:
                events.append(Event(
                    timestamp=0.0,
                    event="mode_stats",
                    actor=player_name,
                    target=None,
                    meta={
                        "mode": mode_key,
                        "stats": mode_data
                    }
                ))
        
        return events

    @staticmethod
    def rank_data_to_events(rank_data: Dict[str, Any], player_name: str) -> List[Event]:
        """ランクデータを共通イベントに変換"""
        events: List[Event] = []
        
        if not rank_data.get("data"):
            return events
        
        data = rank_data["data"]
        current_data = data.get("current_data", {})
        
        events.append(Event(
            timestamp=0.0,
            event="rank_info",
            actor=player_name,
            target=None,
            meta={
                "name": data.get("name"),
                "tag": data.get("tag"),
                "current_tier": current_data.get("currenttier"),
                "current_tier_patched": current_data.get("currenttierpatched"),
                "ranking_in_tier": current_data.get("ranking_in_tier"),
                "mmr_change": current_data.get("mmr_change_to_last_game"),
                "elo": current_data.get("elo"),
                "games_needed_for_rating": current_data.get("games_needed_for_rating")
            }
        ))
        
        return events

    @staticmethod
    def filter_player_events(events: List[Event], player_name: str) -> List[Event]:
        """特定プレイヤーに関連するイベントのみをフィルタリング"""
        filtered_events = []
        
        for event in events:
            if (event.actor == player_name or 
                event.target == player_name or 
                event.meta.get("puuid") == player_name or
                event.event in ["match_start", "match_end", "round_start", "round_end"]):
                filtered_events.append(event)
        
        return filtered_events

    @staticmethod
    def calculate_performance_metrics(events: List[Event], player_name: str) -> Dict[str, Any]:
        """イベントからパフォーマンス指標を計算"""
        metrics = {
            "total_kills": 0,
            "total_deaths": 0,
            "total_assists": 0,
            "total_rounds": 0,
            "first_bloods": 0,
            "first_deaths": 0,
            "headshot_percentage": 0.0,
            "average_damage_per_round": 0.0,
            "rounds_won": 0,
            "kda_ratio": 0.0
        }
        
        total_damage = 0
        total_headshots = 0
        total_shots = 0
        
        for event in events:
            if event.actor == player_name:
                if event.event == "match_performance":
                    meta = event.meta
                    metrics["total_kills"] += meta.get("kills", 0)
                    metrics["total_deaths"] += meta.get("deaths", 0)
                    metrics["total_assists"] += meta.get("assists", 0)
                    metrics["first_bloods"] += meta.get("first_bloods", 0)
                    metrics["first_deaths"] += meta.get("first_deaths", 0)
                    
                    total_damage += meta.get("damage_made", 0)
                    total_headshots += meta.get("headshots", 0)
                    total_shots += (meta.get("headshots", 0) + 
                                  meta.get("bodyshots", 0) + 
                                  meta.get("legshots", 0))
            
            if event.event == "round_end":
                metrics["total_rounds"] += 1
                # 勝利ラウンドの判定ロジックは必要に応じて実装
        
        # 計算
        if metrics["total_deaths"] > 0:
            metrics["kda_ratio"] = (metrics["total_kills"] + metrics["total_assists"]) / metrics["total_deaths"]
        else:
            metrics["kda_ratio"] = float(metrics["total_kills"] + metrics["total_assists"])
        
        if total_shots > 0:
            metrics["headshot_percentage"] = (total_headshots / total_shots) * 100
        
        if metrics["total_rounds"] > 0:
            metrics["average_damage_per_round"] = total_damage / metrics["total_rounds"]
        
        return metrics