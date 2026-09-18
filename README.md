# シフト希望提出フォーム

Streamlit Cloud 上で動作する、翌月分のシフト希望を集めるフォーム。
提出データの保存先は Google スプレッドシート（GAS 経由）。

## 構成

フロントエンド（画面）とバックエンド（ロジック・外部通信）をレイヤで分離している。
`core` / `services` / `exporters` は **Streamlit に依存しない** ので、
将来 FastAPI などの API サーバへそのまま移せる。

```
form_app.py              Streamlit エントリポイント。画面の流れだけを持つ
core/
  config.py              対象年月の算出、定数、シークレットの解決
  calendar_util.py       日付ラベル・タブ分割・週マトリクスの生成
  models.py              ShiftSubmission（正規化・バリデーション・ペイロード化）
  shift_rules.py         選択肢 → 記録表記（希望なし→出、有給→有 など）
services/
  gas_client.py          GAS への POST / GET。失敗は GasError
  shift_service.py       提出・取得・Excel 用整形・提出状況の照合
exporters/
  excel.py               店長確認用 Excel（openpyxl による装飾）
ui/
  state.py               セッションステートの初期化とキー命名
  form_view.py           基本情報・日ごとの希望・一括入力ダイアログ
  preview.py             カレンダープレビュー
  admin_view.py          店長専用メニュー
gas/
  Code.gs                スプレッドシート側の Apps Script（貼り付け用の控え）
tests/                   pytest（ロジック層 + AppTest によるスモーク）
```

依存の向きは `form_app.py` → `ui` → `services` → `core` の一方向。
`ui` 以外のモジュールで `import streamlit` してはいけない
（唯一の例外は `core/config.py` の `_read_secret`。関数内に閉じ込めてある）。

## 二重提出の防止

確定ボタンの連打で同じシフトが何行も保存されないよう、2 段構えにしている。

1. **アプリ側** — `_do_submit` が `request_id` を見て、
   このセッションで送り終えた内容は二度と送らない（`sent_request_ids`）。
   `is_processing` のようなフラグだけに頼らないのが要点で、連打すると
   再実行が何度も走り、フラグの更新が間に合わない瞬間ができてしまう。
   記録は**送信の前**に行う（送信直後に実行が打ち切られても再送しない）。
   補助として、(a) 送信中の画面にはボタンを描画しない、
   (b) 画面下部を `st.empty()` にして、送信中に前の描画（確定ボタン）が
   ブラウザに残らないようにする、(c) `_do_submit` の中で `st.*` を呼ばない
   ——Streamlit は `st.*` の地点で保留中の再実行に切り替わるため、
   通信と状態更新の間に `st.*` があるとそこで打ち切られて再送になる。
2. **スプレッドシート側** — `ShiftSubmission.request_id()` が提出内容から
   決まる ID を作り、GAS が非表示シート `_提出ID` と突き合わせて
   2 件目以降を捨てる。リロードや別タブからの再提出も、
   通信リトライで同じ内容が二重に届いた場合もここで止まる。
   内容を直して出し直せば別 ID になるので、修正版はちゃんと保存される。

`gas/Code.gs` を変更したら、Apps Script エディタに貼り付けたうえで
「デプロイを管理」からウェブアプリを新しいバージョンに更新すること
（ここを忘れると 2 の防御が効かない）。

## シークレット

`gas_url` と `admin_password` の 2 つ。環境変数（`GAS_URL` / `ADMIN_PASSWORD`）を優先し、
無ければ `st.secrets` を読む。Streamlit Cloud では従来どおり Secrets に設定する。

ローカル実行時は環境変数でも `.streamlit/secrets.toml` でもよい。

## 実行

```bash
pip install -r requirements.txt
streamlit run form_app.py
```

## テスト

```bash
pip install pytest
python -m pytest
```

## デプロイの流れ

Streamlit Cloud は**追跡ブランチへの push を検知して即アプリを再起動する**。
再起動すると入力中の利用者のセッションが飛ぶため、
アプリ側のメンテナンス枠（00:00〜04:00 JST）の中でだけ本番を更新する。

```
develop  ← 日中いつでも push してよい（本番に影響なし）
   │
   │ 毎日 02:00 JST に自動マージ（pytest が緑のときだけ）
   ▼
main     ← Streamlit Cloud が追跡。ここが動いた時だけ再デプロイ
```

- 普段の作業は `develop` に対して行う。`main` は直接触らない。
- 反映を待てないときは Actions 画面の
  「メンテナンス枠で本番へ反映」→ Run workflow で手動実行できる
  （ただし利用者のセッションは飛ぶので、日中は避ける）。
- 自動マージには GitHub リポジトリの
  Settings → Actions → General → Workflow permissions が
  **Read and write permissions** になっている必要がある。
- スケジュール実行はリポジトリに60日間活動がないと GitHub 側で自動停止される。
