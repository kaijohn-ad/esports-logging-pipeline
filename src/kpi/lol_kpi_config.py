"""
League of Legends KPI設定モジュール

KPI計算に使用する設定値を管理
"""


class LoLKPIConfig:
    """LoL KPI計算の設定クラス"""
    
    # KPI重み付け設定
    KDA_WEIGHT = 10  # KDAの重み（最大50点）
    CS_WEIGHT = 2   # CS/10minの重み（最大25点） 
    VISION_WEIGHT = 5  # ビジョンスコアの重み（最大15点）
    DAMAGE_WEIGHT = 20  # ダメージ効率の重み（最大10点）
    
    # オブジェクト貢献度スコア
    TOWER_SCORE = 10
    INHIBITOR_SCORE = 15
    NEXUS_SCORE = 25
    DRAGON_SCORE = 20
    BARON_SCORE = 30
    RIFTHERALD_SCORE = 15
    
    # 分析閾値
    EXCELLENT_KDA = 4.0
    GOOD_KDA = 2.5
    EXCELLENT_CS = 8.0  # CS/min
    GOOD_CS = 6.0
    EXCELLENT_VISION = 2.0  # per min
    GOOD_VISION = 1.2