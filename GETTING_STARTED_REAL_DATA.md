# 🚀 実際の試合データを今すぐ試す方法

金曜夜スプリントで**killイベント処理パイプラインは完成**しているので、実際のプレイヤーデータで試すことができます！

## 📝 **5分でセットアップ**

### ステップ1: Riot API Key取得（2分）

1. **[Riot Developer Portal](https://developer.riotgames.com/) にアクセス**
2. **Riotアカウントでログイン**
3. **「REGENERATE API KEY」をクリック**
4. **24時間有効の開発用キーをコピー**

### ステップ2: 環境設定（1分）

プロジェクトルートに `.env` ファイルを作成：

```bash
# .env
RIOT_API_KEY=RGAPI-あなたのAPIキーをここに貼り付け
RIOT_REGION=jp1
```

### ステップ3: 依存関係確認（1分）

```bash
# 必要な依存関係をインストール（既に実行済みなら不要）
pip install python-dotenv
```

### ステップ4: 実行（1分）

```bash
# あなたのLoLサマナー名に置き換えて実行
python real_data_test.py --lol-player "あなたのサマナー名"
```

## 🎯 **期待される結果**

```
🚀 実際の試合データ取得テスト
==================================================

🎮 LoL データ取得テスト
サマナー名: あなたのサマナー名
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
5. データベース保存テスト...
   ✅ データベース保存完了: data/real_test_lol.db
   ✅ 保存されたkillイベント: 42件

🎉 実際のデータ取得に成功しました！
```

## 📈 **成功したら次にできること**

### 1. **KPI分析**
```bash
# あなたのパフォーマンス分析
python src/log_pipeline.py analyze-performance --summoner-name "あなたのサマナー名"
```

### 2. **複数マッチ分析**
```bash
# 最新5試合のkillイベント分析
python real_data_test.py --lol-player "あなたのサマナー名"
# 設定でmatch_countを変更可能
```

### 3. **データベース確認**
```bash
# SQLiteデータベースの内容確認
python -c "
import sqlite3
conn = sqlite3.connect('data/real_test_lol.db')
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM events WHERE event_type = \"kill\"')
print(f'保存されたkillイベント数: {cursor.fetchone()[0]}')
cursor.execute('SELECT * FROM events LIMIT 5')
for row in cursor.fetchall():
    print(row)
"
```

## ⚡ **トラブルシューティング**

### よくある問題

1. **`Forbidden` エラー**
   - APIキーが正しく設定されているか確認
   - 24時間の有効期限をチェック

2. **プレイヤーが見つからない**
   - サマナー名のスペルチェック
   - リージョン確認（jp1, kr, na1など）

3. **レート制限**
   - 20リクエスト/2分の制限
   - 2分待ってから再実行

## 🎮 **他のプレイヤーでテストする場合**

```bash
# 有名プレイヤーで試す（例）
python real_data_test.py --lol-player "Hide on bush"  # Faker
python real_data_test.py --lol-player "Dopa"         # Apdo
```

## 🔥 **現在動作が確認されている機能**

- ✅ **プレイヤー情報取得**
- ✅ **マッチ履歴取得**  
- ✅ **マッチ詳細・タイムライン取得**
- ✅ **killイベント正規化・抽出**
- ✅ **SQLiteデータベース保存**
- ✅ **エラーハンドリング・レート制限対応**

## 🚀 **このテストが成功したら...**

**あなたの実際の試合データでパフォーマンス分析、KPI計算、LLMによるフィードバック生成を試すことができます！**

既存の金曜夜スプリントで完成した：
- **LoL killイベント処理パイプライン** ✅
- **SQLiteストレージ** ✅  
- **KPI計算機能** ✅
- **LLM分析基盤** ✅

すべてがあなたの実データで動作します！ 