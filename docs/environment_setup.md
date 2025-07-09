# 環境設定ガイド - 実際の試合データ利用

このガイドでは、実際のLoLとVALORANTの試合データを取得するための環境設定手順を説明します。

## 🎯 必要なAPIキー

### 1. Riot Games API Key（LoL用）- **必須**

**取得手順：**
1. [Riot Developer Portal](https://developer.riotgames.com/) にアクセス
2. Riot アカウントでサインイン
3. ダッシュボードで「REGENERATE API KEY」をクリック
4. 開発用キー（24時間有効）を取得

**制限事項：**
- 開発用キー：20リクエスト/2分、24時間で期限切れ
- 本番用キー：申請が必要、より高いレート制限

### 2. VALORANT API - **APIキー不要**

**Henrik Dev API使用：**
- 無料で利用可能
- APIキー不要
- プレイヤー名#TAG形式で検索

## 🔧 環境設定手順

### ステップ1: 依存関係インストール

```bash
# 追加依存関係をインストール
pip install python-dotenv aiohttp

# 既存依存関係が最新か確認
pip install -r requirements.txt
```

### ステップ2: 環境変数ファイル作成

プロジェクトルートに `.env` ファイルを作成：

```bash
# .env ファイルの内容
# Riot Games API Key (LoL用)
RIOT_API_KEY=RGAPI-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
# リージョン設定
RIOT_REGION=jp1

# プレイヤー設定（デフォルト値）
DEFAULT_LOL_SUMMONER=YourSummonerName
DEFAULT_VALORANT_PLAYER=YourValorantName#TAG

# OpenRouter API Key (LLM分析用、オプション)
OPENROUTER_API_KEY=sk-or-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### ステップ3: 実行テスト

```bash
# LoLデータ取得テスト
python real_data_test.py --lol-player "YourSummonerName"

# VALORANTデータ取得テスト  
python real_data_test.py --valorant-player "YourPlayerName#TAG"

# 両方同時テスト
python real_data_test.py --lol-player "YourSummonerName" --valorant-player "YourPlayerName#TAG"
```

## 📋 テスト対象機能

### LoL API テスト内容
1. ✅ プレイヤー（サマナー）情報取得
2. ✅ 最新マッチ一覧取得（3試合）
3. ✅ マッチ詳細データ取得
4. ✅ タイムラインデータ取得
5. ✅ killイベント正規化・抽出
6. ✅ SQLiteデータベース保存

### VALORANT API テスト内容
1. ✅ プレイヤー情報とマッチ履歴取得
2. ✅ マッチ詳細データ取得
3. ✅ round_killsイベント抽出
4. ✅ killイベントへの正規化・変換
5. ✅ SQLiteデータベース保存

## 🚀 期待される結果

### 成功時の出力例

```
🚀 実際の試合データ取得テスト
==================================================

🎮 LoL データ取得テスト
サマナー名: YourSummonerName
リージョン: jp1
----------------------------------------
1. サマナー情報を取得中...
   ✅ PUUID: abcd1234...
   ✅ レベル: 125
2. 最新マッチを取得中...
   ✅ 取得マッチ数: 3
3. マッチ詳細を取得中...
   ✅ マッチID: JP1_123456789
   ✅ ゲーム時間: 1847秒
   ✅ ゲームモード: CLASSIC
4. killイベントを抽出中...
   ✅ 総イベント数: 245
   ✅ killイベント数: 42
   🎯 killイベント例:
      Kill #1: 324.5s - Player 1 → Player 6
      Kill #2: 387.2s - Player 3 → Player 8
      Kill #3: 445.8s - Player 2 → Player 7
5. データベース保存テスト...
   ✅ データベース保存完了: data/real_test_lol.db
   ✅ 保存されたkillイベント: 42件

🎯 VALORANT データ取得テスト
プレイヤー: YourPlayerName#TAG
----------------------------------------
1. プレイヤー情報を取得中...
   ✅ 取得マッチ数: 1
2. マッチ詳細を取得中...
   ✅ マッチID: abc123-def456-ghi789
   ✅ マップ: Haven
   ✅ ゲームモード: Competitive
3. killイベントを抽出中...
   ✅ 総イベント数: 24
   ✅ round_killsイベント数: 24
   ✅ 変換後killイベント数: 156
4. データベース保存テスト...
   ✅ データベース保存完了: data/real_test_valorant.db
   ✅ 保存されたkillイベント: 156件

📊 テスト結果サマリー
==================================================
LoL: ✅ 成功
   詳細: LoL: 42 kill events from YourSummonerName
VALORANT: ✅ 成功
   詳細: VALORANT: 156 kill events from YourPlayerName#TAG

🎉 実際のデータ取得に成功しました！

🚀 次のステップ:
1. データベースに保存されたkillイベントを確認
2. KPI計算機能でパフォーマンス分析
3. LLM（OpenRouter）を使用したフィードバック生成
4. 定期的なデータ収集の自動化
```

## ⚠️ よくある問題と解決方法

### 1. Riot API Key関連

**問題**: `Forbidden` エラー
**解決**: 
- APIキーが正しく設定されているか確認
- APIキーの有効期限（24時間）をチェック
- リージョンが正しいか確認（jp1, kr, na1など）

**問題**: `Rate limit exceeded`
**解決**:
- 20リクエスト/2分の制限に達した
- 2分待ってから再実行

### 2. VALORANT API関連

**問題**: プレイヤーが見つからない
**解決**:
- プレイヤー名#TAG形式を確認
- TAG部分の大文字・小文字をチェック
- 最近のマッチ履歴があるか確認

### 3. 環境設定関連

**問題**: `ModuleNotFoundError`
**解決**:
```bash
pip install python-dotenv aiohttp
```

**問題**: `.env`ファイルが読み込まれない
**解決**:
- ファイルがプロジェクトルートにあるか確認
- ファイル名が正確に`.env`か確認
- 権限設定を確認

## 🔒 セキュリティ注意事項

1. **APIキーの管理**:
   - `.env`ファイルをGitにコミットしない
   - `.gitignore`に`.env`が含まれているか確認

2. **個人情報保護**:
   - プレイヤー名やPUUIDの扱いに注意
   - 公開リポジトリでは実際の名前を使用しない

3. **レート制限の遵守**:
   - API制限を超えないよう注意
   - 自動化時は適切な間隔を設定

## 📈 次のステップ

実際のデータ取得が成功したら：

1. **KPI分析**: 既存のKPI計算機能で試合パフォーマンスを分析
2. **LLM分析**: OpenRouter APIを使用したフィードバック生成
3. **自動化**: 定期的なデータ収集の仕組み構築
4. **可視化**: 週次KPIダッシュボードの作成 