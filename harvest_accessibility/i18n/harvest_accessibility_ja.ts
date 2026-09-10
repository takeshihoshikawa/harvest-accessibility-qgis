<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="ja_JP">
<context>
    <name>HarvestAccessibilityPlugin</name>
    <message>
        <source>Run…</source>
        <translation>実行…</translation>
    </message>
    <message>
        <source>Harvest Accessibility</source>
        <translation>搬出距離</translation>
    </message>
</context>
<context>
    <name>HarvestAccessibilityAlg</name>
    <message>
        <source>Harvest Accessibility</source>
        <translation>搬出距離</translation>
    </message>
    <message>
        <source>Inputs: operation polygon, forest road lines (also used as network), landing points (multiple OK).
1) Create grid points within polygon (p1)
2) Shortest straight line to road -&gt; d1, endpoint on road -&gt; p2
3) Shortest path on road network from p2 to the nearest landing -&gt; d2 (NULL if unreachable)
4) HTML result report.
NOTE: Use a projected CRS in metres.

Advanced: enable debug mode to load intermediate layers into the project.</source>
        <translation>入力：作業区域ポリゴン、作業道ライン（ネットワークとしても使用）、土場点（複数可）。
1) ポリゴン内にグリッド点（p1）を作成
2) 各グリッド点から最近傍の林道までの直線距離 → d1、道路上の最近傍点 → p2
3) p2から最近傍土場までの道路ネットワーク最短距離 → d2（未到達の場合はNULL）
4) HTML結果レポートを出力。
注意：メートル系投影座標系を使用してください。

詳細設定：デバッグモードを有効にすると中間レイヤーをプロジェクトに追加します。</translation>
    </message>
    <message>
        <source>Operation area polygon</source>
        <translation>作業区域ポリゴン</translation>
    </message>
    <message>
        <source>Forest road lines (also network)</source>
        <translation>作業道ライン（ネットワーク兼用）</translation>
    </message>
    <message>
        <source>Landing points (multiple OK)</source>
        <translation>土場点（複数可）</translation>
    </message>
    <message>
        <source>Grid spacing (m)</source>
        <translation>グリッド間隔 (m)</translation>
    </message>
    <message>
        <source>Network snapping tolerance (m)</source>
        <translation>スナップ許容誤差 (m)</translation>
    </message>
    <message>
        <source>Split roads at intersections before routing</source>
        <translation>ルーティング前に交差点で道路を自動分割</translation>
    </message>
    <message>
        <source>Result report</source>
        <translation>結果レポート</translation>
    </message>
    <message>
        <source>Debug mode (add intermediate layers to project)</source>
        <translation>デバッグモード（中間レイヤーをプロジェクトに追加）</translation>
    </message>
    <message>
        <source>Invalid input layers.</source>
        <translation>入力レイヤーが無効です。</translation>
    </message>
    <message>
        <source>Operation area polygon has no features.</source>
        <translation>作業区域ポリゴンにフィーチャがありません。</translation>
    </message>
    <message>
        <source>Forest roads layer has no features.</source>
        <translation>作業道レイヤーにフィーチャがありません。</translation>
    </message>
    <message>
        <source>Polygon CRS is geographic (degrees). Reproject to a projected CRS in metres.</source>
        <translation>ポリゴンのCRSが地理座標系（度）です。メートル系の投影座標系に再投影してください。</translation>
    </message>
    <message>
        <source>Polygon CRS unit is &apos;{}&apos;, not metres. Grid spacing and distances will be incorrect. Reproject to a metric CRS.</source>
        <translation>ポリゴンのCRS単位が「{}」です（メートルではありません）。グリッド間隔と距離が正しく計算されません。メートル系CRSに再投影してください。</translation>
    </message>
    <message>
        <source>Road layer CRS ({}) differs from polygon CRS ({}). Reproject all layers to the same CRS.</source>
        <translation>林道レイヤーのCRS（{}）がポリゴンのCRS（{}）と異なります。全レイヤーを同じCRSに再投影してください。</translation>
    </message>
    <message>
        <source>Landing layer CRS ({}) differs from polygon CRS ({}). Reproject all layers to the same CRS.</source>
        <translation>土場レイヤーのCRS（{}）がポリゴンのCRS（{}）と異なります。全レイヤーを同じCRSに再投影してください。</translation>
    </message>
    <message>
        <source>1) Creating grid points (p1)...</source>
        <translation>1) グリッド点（p1）を作成中...</translation>
    </message>
    <message>
        <source>No grid points fall within the operation polygon. Try a smaller grid spacing.</source>
        <translation>作業区域ポリゴン内にグリッド点がありません。グリッド間隔を小さくしてください。</translation>
    </message>
    <message>
        <source>2) Computing shortest lines to roads (d1) and nearest points (p2)...</source>
        <translation>2) 道路への最短距離（d1）と最近傍点（p2）を計算中...</translation>
    </message>
    <message>
        <source>3) Computing shortest path along road network to nearest landing (d2)...</source>
        <translation>3) 最近傍土場までの道路ネットワーク最短経路（d2）を計算中...</translation>
    </message>
    <message>
        <source>Landing layer has no features.</source>
        <translation>土場レイヤーにフィーチャがありません。</translation>
    </message>
    <message>
        <source>3a) Splitting roads at intersections...</source>
        <translation>3a) 交差点で道路を分割中...</translation>
    </message>
    <message>
        <source>    -&gt; {} segments after split.</source>
        <translation>    -> 分割後のセグメント数: {}</translation>
    </message>
    <message>
        <source>Processing cancelled by user.</source>
        <translation>ユーザーによって処理がキャンセルされました。</translation>
    </message>
    <message>
        <source>No valid landing points were found (all geometries empty?).</source>
        <translation>有効な土場点が見つかりませんでした（ジオメトリがすべて空です）。</translation>
    </message>
    <message>
        <source>Note: routing output has no &apos;cost&apos; field; using geometry length for d2.</source>
        <translation>注意：ルーティング出力に「cost」フィールドがないため、ジオメトリ長をd2として使用します。</translation>
    </message>
    <message>
        <source>Routing output has no &apos;tree_id&apos; field. Ensure p2 has &apos;tree_id&apos; attribute.</source>
        <translation>ルーティング出力に「tree_id」フィールドがありません。p2に「tree_id」属性があることを確認してください。</translation>
    </message>
    <message>
        <source>All grid points are unreachable from all landings. Check that the road network is connected, landing points are on or near the road, and the snapping tolerance is sufficient.</source>
        <translation>全グリッド点がすべての土場から到達不能です。道路ネットワークが接続されているか、土場点が道路上または近傍にあるか、スナップ許容誤差が十分かを確認してください。</translation>
    </message>
    <message>
        <source>Unexpected statistics output (no &apos;min&apos; field).</source>
        <translation>統計出力が予期しない形式です（「min」フィールドがありません）。</translation>
    </message>
    <message>
        <source>4) Computing summary statistics...</source>
        <translation>4) 集計統計を計算中...</translation>
    </message>
    <message>
        <source>WARNING: d2_mean is None — no grid points could be routed to any landing. Check that the road network is connected and the snapping tolerance is sufficient.</source>
        <translation>警告：d2の平均がNoneです — いずれの土場にも到達できるグリッド点がありません。道路ネットワークの接続とスナップ許容誤差を確認してください。</translation>
    </message>
    <message>
        <source>Debug: no project context, skipping layer output.</source>
        <translation>デバッグ：プロジェクトコンテキストがないため、レイヤー出力をスキップします。</translation>
    </message>
    <message>
        <source>Unexpected error during processing: {}</source>
        <translation>処理中に予期しないエラーが発生しました: {}</translation>
    </message>
</context>
</TS>
