# AC_Jo

Assetto Corsaを、自然文で目標を伝えて動かすエージェント環境を作るプロジェクトです。MineDojoを参考に、**タスク記述 → 環境観測 → 行動 → 結果の観測**を繰り返す共通ループを用意します。

## 今あるもの

- `DrivingGoal`: ドリフト、タイムアタック、追従、一般走行のタスク表現
- `Observation` / `Action` / `StepResult`: 環境とエージェントの共通データ形式
- `DrivingEnvironment`: シミュレーター接続アダプターのプロトコル
- `HeuristicAgent`: 低速・低入力の配線確認用ベースライン
- `run_episode`: 行動時間とステップ数を制限する実行ループ

自然文パーサーは日本語・英語の基本的なキーワード、速度、周回数だけを扱う初期版です。汎用的な言語理解や学習済み運転能力はありません。ドリフトや追従には、専用ポリシーと対象車両の観測が必要です。

## 使い方

Python 3.11以上で、`acjo.py`をプロジェクトに置いて利用します。

```python
from acjo import HeuristicAgent, Observation, parse_goal

goal = parse_goal("ニュルブルクリンクを安全に3周タイムアタック")
print(goal)
```

環境アダプターは `reset()`、`step(action)`、`close()` を実装します。`Observation` の速度はm/s、角度はrad、時間は秒です。アダプターはユーザーが起動したゲームへ接続し、ゲーム自体を勝手に起動・終了しない設計です。

```python
from acjo import HeuristicAgent, parse_goal, run_episode

final_state = run_episode(
    environment=my_assetto_corsa_adapter,
    agent=HeuristicAgent(speed_limit_kmh=40),
    goal=parse_goal("安全に40 km/h以下で走る"),
    max_steps=500,
)
```

## 次の段階

1. Assetto Corsaのテレメトリーと入力ブリッジ
2. 車両、コース、ラップ、接触などの観測項目
3. 自然文から再現可能なタスク設定への変換
4. 視覚・状態を使う制御ポリシーと安全停止
5. タイムアタック、ドリフト、追従の評価とリプレイ

このブランチは最初のAPI骨格です。Assetto Corsaとの実接続や運転性能はまだ実装・検証されていません。

参考: [MineDojo](https://github.com/MineDojo/MineDojo) — 自然言語タスクと統一環境APIを備えた embodied-agent 研究フレームワーク。
