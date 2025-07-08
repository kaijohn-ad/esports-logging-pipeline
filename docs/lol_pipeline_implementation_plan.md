# League of Legends パイプライン実装計画書

## 1. 概要

本文書は、eSportsログ取得・解析パイプラインのうち、League of Legends（LoL）部分の実装計画を定義します。既存のコードベースを基に、より堅牢で実用的なLoLデータ収集・分析システムを構築することを目的とします。LLMによるフィードバック生成には、複数のモデルを統一APIで利用できるOpenRouterを採用します。

## 2. 現在の実装状況分析

### 2.1 既存コンポーネント

| コンポーネント | 実装状況 | 機能レベル | 改善が必要な点 |
|-------------|---------|-----------|---------------|
| `LoLFetcher` | 基本実装済み | 最小限 | エラーハンドリング、レート制限対応 |
| `LoLCanonizer` | 基本実装済み | 限定的 | イベントタイプの拡張、メタデータ強化 |
| `Event` スキーマ | 完成 | 十分 | - |
| SQLite DB | 完成 | 十分 | - |
| CLI インターフェイス | 基本実装済み | 最小限 | UX改善、設定管理 |

### 2.2 技術的負債

- **エラーハンドリング不足**: API障害時の適切な処理が未実装
- **レート制限未対応**: Riot APIの制限（20 req/2 min）に対する制御なし
- **限定的なイベント対応**: CHAMPION_KILLのみ、その他のイベントは未対応
- **設定管理不足**: API キー、サマナー名などの設定が分散

## 3. 実装フェーズ

### フェーズ1: 基盤強化（優先度: 高）

#### 3.1 LoLFetcher クラスの拡張

**目標**: 安定したデータ収集基盤の構築

**実装内容**:
```python
class LoLFetcher:
    def __init__(self, api_key: str, region: str = "jp1"):
        self.watch = LolWatcher(api_key)
        self.region = region
        self.rate_limiter = RateLimiter(20, 120)  # 20 req/2 min
        
    async def fetch_with_retry(self, func, *args, max_retries=3):
        """指数バックオフによるリトライ機能"""
        
    def fetch_match_details(self, match_id: str) -> Dict:
        """マッチ詳細情報の取得"""
        
    def fetch_summoner_rank(self, summoner_id: str) -> Dict:
        """サマナーランク情報の取得"""
```

**技術要件**:
- **レート制限**: `asyncio.Semaphore` を使用した同時実行制御
- **エラーハンドリング**: `ApiError` の種類に応じた適切なリトライ戦略
- **ログ**: 構造化ログによる詳細な動作記録
- **メトリクス**: API使用量とエラー率の監視

#### 3.2 LoLCanonizer の拡張

**目標**: 包括的なイベント正規化

**追加対象イベント**:
- `CHAMPION_KILL` → `kill`, `death`, `assist`
- `SKILL_LEVEL_UP` → `skill_levelup`
- `ITEM_PURCHASED` → `item_buy`
- `ITEM_SOLD` → `item_sell`
- `WARD_PLACED` → `ward_place`
- `WARD_KILL` → `ward_destroy`
- `BUILDING_KILL` → `objective_destroy`
- `MONSTER_KILL` → `monster_kill`

**メタデータ強化**:
```python
class Event(BaseModel):
    timestamp: float
    event: str
    actor: str
    target: str | None = None
    meta: Dict[str, Any] = Field(default_factory=dict)
    # 追加フィールド
    position: tuple[int, int] | None = None
    team_id: int | None = None
    match_context: Dict[str, Any] = Field(default_factory=dict)
```

#### 3.3 データ検証機能

**目標**: データ品質の保証

**実装内容**:
```python
class DataValidator:
    def validate_match_completeness(self, match_data: Dict) -> ValidationResult:
        """マッチデータの完全性チェック"""
        
    def validate_timeline_consistency(self, timeline: Dict) -> ValidationResult:
        """タイムラインの整合性チェック"""
        
    def detect_anomalies(self, events: List[Event]) -> List[AnomalyReport]:
        """異常データの検出"""
```

### フェーズ2: 分析機能強化（優先度: 中）

#### 3.4 LoL特有KPI機能

**基本KPI**:
- **KDA比**: `(kills + assists) / deaths`
- **CS/10min**: `(creep_score / game_duration) * 10`
- **ゴールド効率**: `gold_earned / game_duration`
- **ダメージ効率**: `damage_dealt / gold_earned`

**上級KPI**:
- **ビジョンスコア**: ワード設置・破壊・時間の複合指標
- **オブジェクト貢献度**: ドラゴン・バロン・タワーへの関与度
- **レーン効率**: CS差、経験値差、プレート取得
- **チーム戦パフォーマンス**: チーム戦でのキル関与率

**実装例**:
```python
class LoLKPICalculator:
    def calculate_basic_kpi(self, match_id: str) -> Dict[str, float]:
        """基本KPIの算出"""
        
    def calculate_advanced_kpi(self, match_id: str) -> Dict[str, float]:
        """上級KPIの算出"""
        
    def calculate_trend_analysis(self, summoner_id: str, days: int = 30) -> TrendReport:
        """時系列分析"""
```

#### 3.5 LLMフィードバック生成（OpenRouter）

**目標**: 個人化されたフィードバック生成

**実装内容**:
```python
class LoLLLMAnalyzer:
    def __init__(self, api_key: str, model: str = "anthropic/claude-3-haiku"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://openrouter.ai/api/v1"
        
    async def analyze_performance(self, summoner_id: str, match_count: int = 5) -> str:
        """パフォーマンス分析"""
        prompt = self._build_performance_prompt(summoner_id, match_count)
        return await self._call_openrouter(prompt)
        
    async def suggest_improvements(self, kpi_data: Dict, weak_points: List[str]) -> str:
        """改善提案"""
        prompt = self._build_improvement_prompt(kpi_data, weak_points)
        return await self._call_openrouter(prompt)
        
    async def analyze_champion_performance(self, champion: str, match_data: List[Dict]) -> str:
        """チャンピオン特化分析"""
        prompt = self._build_champion_analysis_prompt(champion, match_data)
        return await self._call_openrouter(prompt)
        
    async def _call_openrouter(self, prompt: str) -> str:
        """OpenRouter API呼び出し"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://localhost:3000",
            "X-Title": "LoL Pipeline"
        }
        
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1000,
            "temperature": 0.7
        }
        
                 async with aiohttp.ClientSession() as session:
             async with session.post(
                 f"{self.base_url}/chat/completions",
                 headers=headers,
                 json=payload
             ) as response:
                 result = await response.json()
                 return result["choices"][0]["message"]["content"]
```

**OpenRouterの利点**:
- **統一API**: 複数のLLMプロバイダーを統一インターフェイスで利用
- **フォールバック**: 主要モデルが利用できない場合の代替モデル自動選択
- **コスト最適化**: 用途に応じたモデル選択による費用効率化
- **レート制限管理**: プロバイダー別のレート制限を自動処理

**対応モデル**:
- **Claude系**: `anthropic/claude-3-haiku`, `anthropic/claude-3-sonnet`
- **GPT系**: `openai/gpt-4`, `openai/gpt-3.5-turbo`
- **Gemini系**: `google/gemini-pro`
- **オープンソース**: `mistralai/mistral-7b-instruct`

### フェーズ3: 運用・保守性強化（優先度: 低）

#### 3.6 設定管理システム

**設定ファイル例** (`config/lol_config.yaml`):
```yaml
riot_api:
  key: "${RIOT_API_KEY}"
  region: "jp1"
  rate_limit:
    requests_per_period: 20
    period_seconds: 120

summoner:
  name: "SampleSummoner"
  track_matches: 10
  
kpi:
  calculation_interval: 3600  # 1時間
  retention_days: 90

llm:
  provider: "openrouter"
  api_key: "${OPENROUTER_API_KEY}"
  base_url: "https://openrouter.ai/api/v1"
  model: "anthropic/claude-3-haiku"  # デフォルトモデル
  fallback_models:
    - "openai/gpt-3.5-turbo"
    - "google/gemini-pro"
  max_tokens: 1000
  temperature: 0.7
  timeout: 30
  
logging:
  level: "INFO"
  format: "structured"
```

#### 3.7 監視・アラート機能

**実装内容**:
- **ヘルスチェック**: API応答時間、エラー率監視
- **データ品質監視**: 欠損データ、異常値の検出
- **アラート**: Slack webhook による通知

## 4. 品質保証戦略

### 4.1 テスト戦略

#### 4.1.1 ユニットテスト
```python
# tests/test_lol_fetcher.py
class TestLoLFetcher:
    def test_rate_limiting(self):
        """レート制限が正しく動作するかテスト"""
        
    def test_error_handling(self):
        """エラーハンドリングのテスト"""
        
    def test_data_parsing(self):
        """データパース処理のテスト"""
```

#### 4.1.2 統合テスト
- **API統合テスト**: 実際のRiot APIとの接続テスト
- **データパイプラインテスト**: E2Eでのデータ流れテスト
- **パフォーマンステスト**: 大量データ処理のテスト

#### 4.1.3 モックデータ
```python
# tests/fixtures/sample_match_data.json
{
  "match_id": "JP1_123456789",
  "timeline": { ... },
  "match_details": { ... }
}
```

### 4.2 継続的インテグレーション

**GitHub Actions ワークフロー**:
```yaml
name: LoL Pipeline CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run tests
        run: pytest tests/ -v --cov=src/
      - name: Run linting
        run: flake8 src/
```

## 5. 実装スケジュール

### 5.1 マイルストーン

| フェーズ | 期間 | 主要成果物 |
|---------|------|-----------|
| フェーズ1 | 2週間 | 強化されたLoLFetcher、拡張LoLCanonizer |
| フェーズ2 | 2週間 | KPI機能、LLMフィードバック生成機能（OpenRouter） |
| フェーズ3 | 1週間 | 設定管理、監視機能 |

### 5.2 週次計画

**第1週**:
- LoLFetcher のエラーハンドリング実装
- レート制限機能の実装
- 基本的なユニットテスト作成

**第2週**:
- LoLCanonizer のイベントタイプ拡張
- データ検証機能の実装
- 統合テストの作成

**第3週**:
- 基本KPI機能の実装
- 時系列分析機能の実装
- パフォーマンステストの実施

**第4週**:
- LLMフィードバック生成機能（OpenRouter）
- 設定管理システムの実装
- ドキュメント整備

**第5週**:
- 監視・アラート機能の実装
- 最終テストとバグ修正
- デプロイメント準備

## 6. リスク管理

### 6.1 技術的リスク

| リスク | 影響度 | 対策 |
|--------|--------|------|
| Riot API仕様変更 | 高 | APIバージョン固定、変更監視 |
| レート制限による性能劣化 | 中 | 効率的なバッチ処理、キャッシュ活用 |
| 大量データ処理の性能問題 | 中 | 非同期処理、データベース最適化 |

### 6.2 運用リスク

| リスク | 影響度 | 対策 |
|--------|--------|------|
| APIキーの流出 | 高 | 環境変数管理、アクセス制御 |
| データ品質の劣化 | 中 | 継続的監視、自動アラート |
| 依存ライブラリの脆弱性 | 低 | 定期的なアップデート、セキュリティ監査 |

## 7. 成功指標

### 7.1 技術指標

- **データ収集成功率**: 95%以上
- **API応答時間**: 平均2秒以内
- **エラー復旧時間**: 5分以内
- **テストカバレッジ**: 80%以上

### 7.2 ユーザビリティ指標

- **セットアップ時間**: 15分以内
- **データ取得コマンド実行時間**: 30秒以内
- **KPI生成時間**: 10秒以内

## 8. 今後の拡張計画

### 8.1 短期拡張（3ヶ月以内）

- **リアルタイムデータ収集**: Spectator APIの活用
- **より詳細なKPI**: レーン別、時間帯別分析
- **Web UI**: データ可視化インターフェイス

### 8.2 中長期拡張（6ヶ月以降）

- **機械学習**: 勝敗予測、プレイスタイル分析
- **他タイトルとの連携**: VALORANT、Overwatch 2との統合
- **クラウドデプロイ**: スケーラブルなインフラ構築

---

**作成日**: 2025年1月18日  
**バージョン**: 1.0  
**作成者**: Claude AI Assistant 