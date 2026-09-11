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
        <translation>集材・搬出距離</translation>
    </message>
</context>
<context>
    <name>HarvestAccessibilityAlg</name>
    <message>
        <source>Harvest Accessibility</source>
        <translation>集材・搬出距離</translation>
    </message>
    <message>
        <source>Split roads at intersections before routing</source>
        <translation>ルーティング前に交差点で作業道を自動分割</translation>
    </message>
    <message>
        <source>Result report</source>
        <translation>結果レポート</translation>
    </message>
    <message>
        <source>Maximum sample points (0 = no limit)</source>
        <translation>サンプル点数の上限（0 で無制限）</translation>
    </message>
    <message>
        <source>{} of {} landing points have no geometry and were ignored (feature ids: {}). Every sample point will be assigned to the remaining landings.</source>
        <translation>{1} 箇所中 {0} 箇所の土場にジオメトリが無いため無視しました（フィーチャID: {2}）。すべてのサンプル点は残りの土場へ割り当てられます。</translation>
    </message>
    <message>
        <source>{n} of {total} sample points ({pct:.1f}%) could not reach any landing along the road network; their d2 is empty. Check that the road network is connected and that the snapping tolerance is large enough.</source>
        <translation>{total} 点中 {n} 点（{pct:.1f}%）が路網をたどってどの土場にも到達できませんでした（d2 は空）。路網が連結しているか、スナップ許容誤差が十分かを確認してください。</translation>
    </message>
    <message>
        <source>    -&gt; {n} sample points (estimated peak memory {gb:.1f} GB).</source>
        <translation>    -&gt; サンプル点 {n} 点（推定ピークメモリ {gb:.1f} GB）。</translation>
    </message>
    <message>
        <source>{n} sample points exceeds the limit of {lim} (estimated memory {gb:.1f} GB). Use a coarser grid spacing, split the operation area into parts, or raise 'Maximum sample points' in the advanced parameters.</source>
        <translation>サンプル点が {n} 点あり、上限の {lim} 点を超えています（推定メモリ {gb:.1f} GB）。グリッド間隔を粗くするか、作業区域を分割するか、詳細パラメータの「サンプル点数の上限」を引き上げてください。</translation>
    </message>
    <message>
        <source>Invalid input layers.</source>
        <translation>入力レイヤが無効です。</translation>
    </message>
    <message>
        <source>Operation area polygon has no features.</source>
        <translation>作業区域ポリゴンにフィーチャがありません。</translation>
    </message>
    <message>
        <source>Forest roads layer has no features.</source>
        <translation>作業道レイヤにフィーチャがありません。</translation>
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
        <source>1) Creating grid points (p1)...</source>
        <translation>1) グリッド点（p1）を作成中...</translation>
    </message>
    <message>
        <source>2) Computing shortest lines to roads (d1) and nearest points (p2)...</source>
        <translation>2) 作業道への最短距離（d1）と最近傍点（p2）を計算中...</translation>
    </message>
    <message>
        <source>3) Computing shortest path along road network to nearest landing (d2)...</source>
        <translation>3) 最近傍土場までの路網最短経路（d2）を計算中...</translation>
    </message>
    <message>
        <source>Landing layer has no features.</source>
        <translation>土場レイヤにフィーチャがありません。</translation>
    </message>
    <message>
        <source>3a) Splitting roads at intersections...</source>
        <translation>3a) 交差点で作業道を分割中...</translation>
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
        <translation>全グリッド点がすべての土場から到達不能です。路網が接続されているか、土場点が作業道上または近傍にあるか、スナップ許容誤差が十分かを確認してください。</translation>
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
        <translation>警告：d2の平均がNoneです — いずれの土場にも到達できるグリッド点がありません。路網の接続とスナップ許容誤差を確認してください。</translation>
    </message>
    <message>
        <source>Unexpected error during processing: {}</source>
        <translation>処理中に予期しないエラーが発生しました: {}</translation>
    </message>
    <message>
        <source>1) Using supplied tree points as sample points (p1); grid spacing is ignored.</source>
        <translation>1) 与えられた単木ポイントをサンプル点 (p1) として使います。グリッド間隔は無視されます。</translation>
    </message>
    <message>
        <source>2b) Preparing slope and aspect for the felling model...</source>
        <translation>2b) 伐倒モデル用に傾斜と斜面方位を準備しています...</translation>
    </message>
    <message>
        <source>A DEM layer was given, so the download option is ignored.</source>
        <translation>DEM レイヤが指定されているため、ダウンロードの指定は無視されます。</translation>
    </message>
    <message>
        <source>Direct grapple reach from the road (m)</source>
        <translation>道からの直接把持距離 (m)</translation>
    </message>
    <message>
        <source>Do not download</source>
        <translation>ダウンロードしない</translation>
    </message>
    <message>
        <source>Felled stems (butt to top)</source>
        <translation>伐倒した幹（根元から梢まで）</translation>
    </message>
    <message>
        <source>Felled stems need the felling model; supply a DEM (or choose a download source) to get them.</source>
        <translation>伐倒した幹の出力には伐倒モデルが必要です。DEM を指定するか、ダウンロード元を選んでください。</translation>
    </message>
    <message>
        <source>Felling sector half-angle from downslope (deg)</source>
        <translation>伐倒可能な扇形の半角（最大傾斜の下方向から、度）</translation>
    </message>
    <message>
        <source>Hauling lines (grabbed end to road)</source>
        <translation>集材ライン（つかむ側の端から道まで）</translation>
    </message>
    <message>
        <source>No sample points fall within the operation polygon. With a grid, try a smaller spacing; with tree points, check that they overlap the operation area.</source>
        <translation>作業区域ポリゴンの中にサンプル点がありません。グリッドの場合は間隔を小さくしてください。単木ポイントの場合は作業区域と重なっているか確認してください。</translation>
    </message>
    <message>
        <source>Number of candidate roads per sample point</source>
        <translation>サンプル点ごとの候補作業道数</translation>
    </message>
    <message>
        <source>Sample points with distances</source>
        <translation>距離つきサンプル点</translation>
    </message>
    <message>
        <source>Slope at or below which any direction is allowed (deg)</source>
        <translation>全方向に倒せるとみなす傾斜の上限（度）</translation>
    </message>
    <message>
        <source>Slope/aspect smoothing window (m)</source>
        <translation>傾斜・斜面方位の平滑化ウィンドウ (m)</translation>
    </message>
    <message>
        <source>The downloaded DEM could not be opened: {}</source>
        <translation>ダウンロードした DEM を開けませんでした: {}</translation>
    </message>
    <message>
        <source>{} sample points were equidistant from more than one road; keeping one shortest line each.</source>
        <translation>{} 点のサンプル点が複数の作業道から等距離でした。それぞれ最短線を1本だけ残します。</translation>
    </message>
    <message>
        <source>Auto (try each source, best first)</source>
        <translation>自動（取得元を順に試す。解像度の高い順）</translation>
    </message>
    <message>
        <source>DEM file (used instead of downloading)</source>
        <translation>DEM ファイル（ダウンロードの代わりに使う）</translation>
    </message>
    <message>
        <source>    {} gave no DEM here ({}); trying the next source.</source>
        <translation>    {} からは DEM を取得できませんでした（{}）。次の取得元を試します。</translation>
    </message>
    <message>
        <source>No DEM could be downloaded for this area, so the felling model is off and d1 is the plain geometric distance. Give a DEM file under the advanced parameters to turn the model on.</source>
        <translation>この区域の DEM をダウンロードできなかったため、伐倒モデルは無効で、d1 は幾何的な距離のままです。モデルを使うには、詳細パラメータで DEM ファイルを指定してください。</translation>
    </message>
    <message>
        <source>    -&gt; stem reaches the road: {} / within grapple reach: {} / cannot be extracted: {} / outside the DEM: {}</source>
        <translation>    -&gt; 幹が道に届いた: {} 本 / 直接把持の範囲内: {} 本 / 集材できない: {} 本 / DEM の外: {} 本</translation>
    </message>
    <message>
        <source>Keep felling and hauling inside the operation area</source>
        <translation>作業区域の外へ伐倒・集材しない</translation>
    </message>
    <message>
        <source>{n} of {total} sample points cannot be extracted: no felling direction leaves a stem that can be pulled to a road it can reach. Their d1 and d2 are empty and they are left out of the means.</source>
        <translation>{total} 点中 {n} 点が集材できません。どの伐倒方向でも、到達できる道まで幹を引けません。これらの d1・d2 は空にし、平均から除いています。</translation>
    </message>
    <message>
        <source>Tree spacing (m)</source>
        <translation>立木間距離 (m)</translation>
    </message>
    <message>
        <source>DEM download</source>
        <translation>DEM のダウンロード</translation>
    </message>
    <message>
        <source>Barriers</source>
        <translation>障害物</translation>
    </message>
    <message>
        <source>Forest road lines</source>
        <translation>作業道ライン</translation>
    </message>
    <message>
        <source>Individual tree points</source>
        <translation>単木ポイント</translation>
    </message>
    <message>
        <source>Landing points</source>
        <translation>土場点</translation>
    </message>
    <message>
        <source>{layer} is in {src} but the operation area is in {dst}; it is being reprojected. Check that this is intended.</source>
        <translation>{layer} の座標系が {src}、作業区域が {dst} です。変換して使いますが、意図した組み合わせか確認してください。</translation>
    </message>
    <message>
        <source>    {n} points could not be routed at {tol} m; retrying at {retry} m.</source>
        <translation>    {tol} m では {n} 点が経路を引けませんでした。{retry} m で試し直します。</translation>
    </message>
    <message>
        <source>Gap bridged in the road network (m)</source>
        <translation>路網の途切れを繋ぐ許容 (m)</translation>
    </message>
    <message>
        <source>    Landing {fid} sits {d:.1f} m off the road; routed from the nearest point on it.</source>
        <translation>    土場 {fid} は道から {d:.1f} m 離れています。最寄りの道上から経路を引きます。</translation>
    </message>
    <message>
        <source>A lattice at {sp} m over this extent would be about {n} points, past the limit of {lim}. Use a wider tree spacing, split the operation area into parts, or raise 'Maximum sample points' in the advanced parameters.</source>
        <translation>この範囲に {sp} m 間隔で格子を作ると約 {n} 点になり、上限の {lim} 点を超えます。立木間距離を広げるか、作業区域を分割するか、詳細パラメータの「サンプル点数の上限」を引き上げてください。</translation>
    </message>
    <message>
        <source>Gap tolerance {tol} m left points unrouted, so every d2 below comes from {used} m instead. The tolerance decides which part of the network each point ties into, so the other distances moved too -- set it to {used} to reproduce this run.</source>
        <translation>許容 {tol} m では経路を引けない点が残ったため、以下の d2 はすべて {used} m での値です。この値は各点が路網のどこに結びつくかを決めるので、他の距離も変わっています。同じ結果を再現するには {used} を指定してください。</translation>
    </message>
    <message>
        <source>Operation area (polygon)</source>
        <translation>作業区域（ポリゴン）</translation>
    </message>
    <message>
        <source>Forest roads (lines; also the haul network)</source>
        <translation>作業道（ライン。路網としても使用）</translation>
    </message>
    <message>
        <source>Landings (points; more than one is fine)</source>
        <translation>土場（ポイント、複数可）</translation>
    </message>
    <message>
        <source>Barriers (rivers, cliffs; lines or polygons)</source>
        <translation>障害物（河川・崖など、ラインまたはポリゴン）</translation>
    </message>
    <message>
        <source>Individual trees (points; measured tree by tree)</source>
        <translation>単木（ポイント。1本ごとに計算する）</translation>
    </message>
    <message>
        <source>Tree height (field of the tree layer)</source>
        <translation>樹高（単木レイヤのフィールド）</translation>
    </message>
    <message>
        <source>Tree height (m, when no field is given)</source>
        <translation>樹高（m、フィールド未指定時）</translation>
    </message>
    <message>
        <source>The distance the wood is moved: from each felled tree to the forest road, and from there along the network to the nearest landing. Computed tree by tree and reported as averages.

Give it the operation area, the roads and the landings. Tree positions are used where they exist; otherwise trees are placed on a lattice.

A DEM is fetched automatically. The tree is felled in a direction the slope allows, and the distance to the road is measured from whichever end of the stem -- butt or top -- lies nearer to it.

Setting barriers, and whether felling and hauling may leave the operation area, brings the answer closer to what the ground allows.</source>
        <translation>伐採木から作業道までの集材距離と、そこから最寄りの土場までの搬出距離を計算します。立木ごとに計算し、平均値を報告します。

作業区域・作業道・土場を与えてください。立木の位置があればそれを使い、無ければ格子状に立木を置きます。

DEM は自動で取得します。木を斜面の倒せる方向へ倒したうえで、根元と梢のうち道に近い方から道までを集材距離とします。

障害物や、作業区域の外へ伐倒・集材してよいかを設定すると、より現実に近い計算になります。</translation>
    </message>
</context>
<context>
    <name>FetchDemAlg</name>
    <message>
        <source>DEM</source>
        <translation>DEM</translation>
    </message>
    <message>
        <source>Downloads published elevation tiles covering an operation area and writes a DEM in the layer's own CRS.

The main algorithm can fetch its own DEM, so use this when you want the file itself: to reuse one DEM across runs, to inspect or edit it, or to prepare one for a machine without network access.

The DEM is reprojected out of web mercator before being written. That is not cosmetic -- slope computed on mercator tiles comes out roughly 20% too gentle at these latitudes.

Sources: 静岡県 VIRTUAL SHIZUOKA / 産業技術総合研究所 シームレス標高タイル (CC BY 4.0). Credit the source when you publish results.</source>
        <translation>作業区域を覆う公開標高タイルをダウンロードし、レイヤ自身の座標系で DEM を書き出します。

主アルゴリズムも自分で DEM を取得できるので、これはファイルそのものが欲しいときに使います。1つの DEM を複数回の実行で使い回す、中身を確認・編集する、ネットワークの無い機械のために用意する、といった場合です。

書き出す前に Web メルカトルから再投影します。これは見た目の問題ではありません。メルカトルのタイル上で傾斜を計算すると、この緯度ではおよそ 2 割ゆるく出ます。

出典: 静岡県 VIRTUAL SHIZUOKA / 産業技術総合研究所 シームレス標高タイル (CC BY 4.0)。結果を公表するときは出典を明記してください。</translation>
    </message>
    <message>
        <source>Fetch DEM from elevation tiles</source>
        <translation>標高タイルから DEM を取得</translation>
    </message>
    <message>
        <source>Harvest Accessibility</source>
        <translation>Harvest Accessibility</translation>
    </message>
    <message>
        <source>Invalid extent layer.</source>
        <translation>範囲レイヤが無効です。</translation>
    </message>
    <message>
        <source>Margin around the area (m)</source>
        <translation>区域の外側に取る余白 (m)</translation>
    </message>
    <message>
        <source>Operation area (extent to cover)</source>
        <translation>作業区域（覆う範囲）</translation>
    </message>
    <message>
        <source>Output resolution (m; 0 = the tile's own resolution)</source>
        <translation>出力解像度 (m。0 でタイル本来の解像度)</translation>
    </message>
    <message>
        <source>The extent layer is in a geographic CRS. Use a projected CRS in metres so that the margin and output resolution mean metres.</source>
        <translation>範囲レイヤが地理座標系です。余白と出力解像度がメートルとして意味を持つよう、メートル単位の投影座標系を使ってください。</translation>
    </message>
    <message>
        <source>Tile source</source>
        <translation>タイルの取得元</translation>
    </message>
    <message>
        <source>Zoom level (0 = use the source maximum)</source>
        <translation>ズームレベル (0 で取得元の最大値)</translation>
    </message>
</context>
</TS>
