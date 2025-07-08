# eSports Logging Pipeline

League of Legends（LoL）のマッチデータを自動収集・分析し、OpenRouterを活用したLLMによるフィードバックを提供するパイプラインシステムです。

## 🎯 概要

このプロジェクトは、TDD（テスト駆動開発）に基づいて構築された、堅牢で拡張性の高いeSportsデータ分析システムです。

### 主な機能

- **リアルタイムデータ収集**: Riot Games APIを使用したLoLマッチデータの自動取得
- **レート制限対応**: 20 req/2 minの制限に対応した効率的なAPI管理
- **包括的分析**: プレイヤーパフォーマンス、チーム戦績、KPI計算
- **LLMフィードバック**: OpenRouter経由での個人化された改善提案
- **高い信頼性**: エラーハンドリング、リトライ機能、構造化ログ

## 🚀 セットアップ

### 前提条件

- Python 3.12+
- Riot Games API キー
- OpenRouter API キー（LLM機能使用時）

### インストール

```bash
# リポジトリをクローン
git clone <repository-url>
cd eSportsLoggingPipeline

# 依存関係をインストール
pip install -r requirements.txt

# データベースを初期化
python src/log_pipeline.py init
```

### 環境変数設定

```bash
# API キーを設定
export RIOT_API_KEY="your_riot_api_key"
export OPENROUTER_API_KEY="your_openrouter_api_key"
```

### MCP設定（Cursor IDEユーザー向け）

```bash
# MCPサーバー設定をコピー
cp .cursor/mcp.json.example .cursor/mcp.json

# .cursor/mcp.jsonを編集してAPIキーを設定
# YOUR_*_API_KEY_HEREを実際のAPIキーに置き換え
```

⚠️ **セキュリティ注意**: `.cursor/mcp.json`ファイルは実際のAPIキーを含むため、リポジトリには含まれません。必ず個人の環境でのみ設定してください。

## 📊 使用方法

### 基本的な使用方法

```bash
# LoLマッチデータを取得
python src/log_pipeline.py pull-all --summoner-name "YourSummonerName"

# KPIを集計
python src/log_pipeline.py build-kpi

# 週次KPI可視化レポートを生成
python src/log_pipeline.py weekly-kpi --player-id "player1" --weeks 4 --output-dir "data/reports"
```

### プログラマティック使用

```python
from src.log_pipeline import LoLFetcher, WeeklyDashboard

# フェッチャーを初期化
fetcher = LoLFetcher(api_key="your_api_key")

# マッチ詳細を取得
match_data = fetcher.fetch_match_details("match_id")

# プレイヤーパフォーマンスを抽出
performance = fetcher.extract_player_performance(match_data, "puuid")
print(f"KDA: {performance['kda']}")

# 週次KPI可視化ダッシュボードを生成
dashboard = WeeklyDashboard({
    'output_dir': 'data/reports',
    'theme': 'seaborn',
    'include_interactive': True
})

report_files = dashboard.generate_weekly_report(
    player_id="player1",
    week_start="2025-01-13",
    output_dir="data/reports"
)

print(f"Generated reports: {list(report_files.keys())}")
```

## 🧪 テスト実行

```bash
# 全テストを実行
python -m pytest tests/ -v

# カバレッジ付きで実行
python -m pytest tests/ --cov=src/ --cov-report=html
```

## 🏗️ アーキテクチャ

```
eSportsLoggingPipeline/
├── src/
│   └── log_pipeline.py      # メインパイプライン実装
├── tests/                   # テストスイート
├── docs/                    # ドキュメント
├── data/                    # データストレージ
└── requirements.txt         # 依存関係
```

### コアコンポーネント

- **LoLFetcher**: Riot API統合、レート制限、エラーハンドリング
- **RateLimiter**: API呼び出し頻度制御
- **LoLCanonizer**: データ正規化（予定）
- **Event Schema**: 共通データ形式

## 📈 実装済み機能

- ✅ LoLFetcher クラスの機能拡張
- ✅ マッチ詳細情報の取得機能追加
- ✅ レート制限とエラーハンドリング
- ✅ プレイヤー・チームパフォーマンス抽出
- ✅ 週次KPI可視化システム
  - 週次データ集約機能
  - チャンピオン別パフォーマンス分析
  - インタラクティブダッシュボード生成
  - 時系列トレンド分析
- ✅ 包括的なテストスイート
- ✅ Git リポジトリ初期化

## 🔄 開発中の機能

- 🔄 LoLCanonizer の拡張
- 📋 データ検証機能
- 📋 LoL特有KPI機能
- 📋 OpenRouter統合LLMアナライザー

## 🛠️ 技術スタック

- **言語**: Python 3.12
- **API**: Riot Games API, OpenRouter
- **テスト**: pytest, pytest-asyncio
- **データベース**: SQLite
- **ログ**: structlog
- **非同期**: asyncio, aiohttp
- **可視化**: matplotlib, plotly, seaborn, pandas

## 🤝 開発ガイドライン

### TDD アプローチ

このプロジェクトは@t_wadaのTDD実践ガイドに基づいています：

1. **Red**: 失敗するテストを書く
2. **Green**: 最小限の実装で動作させる
3. **Refactor**: 品質を向上させる

### コミット規約

```
feat: 新機能追加
fix: バグ修正
docs: ドキュメント更新
test: テスト追加・修正
refactor: リファクタリング
```

## 📄 ライセンス

MIT License

## 🔗 関連リンク

- [実装計画書](docs/lol_pipeline_implementation_plan.md)
- [設計書](docs/esports_log_pipeline_design.md)
- [Riot Games API](https://developer.riotgames.com/)
- [OpenRouter](https://openrouter.ai/)

---

**開発者**: AI Assistant with TDD  
**最終更新**: 2025年1月18日 