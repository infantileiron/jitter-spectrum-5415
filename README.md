# 北屿通信 · 链路抖动周期定位

为北屿通信10人观测组制作的离线频谱测量台。保留实际采样时间，规则数据计算去趋势/窗函数FFT单侧PSD，不规则数据明确禁用FFT并运行浮动均值Lomb–Scargle；用候选频率联合拟合原波形，复核振幅与相位。不连接真实链路控制，也不把峰值当作故障因果结论。

## 场景与工作日

团队原先靠Excel折线肉眼找重复起伏，存在趋势掩盖周期、不规则采样误用FFT、峰值缺少频率口径三项痛点。上游为离线模拟链路时间观测；系统替代窗口核查、双谱计算与人工复核；下游是站内报告和峰值CSV，不自动调整通信设备。

09:00分析员登录；09:03查看 beiyu_jitter_202611.json 的6链路各480点；09:08选择BY-02的0—479分钟窗口；09:12声明去线性趋势、Hann窗和.005—.1每分钟的LS搜索网格；09:15提交Redis后台；09:18核查点数、实际跨度、规则性和Nyquist；09:22分别阅读FFT PSD和LS解释比例；09:27比较30/80分钟候选与原波形联合幅相；09:32复核缺采样案例的FFT不可用和LS结果；09:36管理员确认最新人工意见接受后归档；09:40只读账号下载真实峰值CSV。

|角色|页面|权限与典型动作|
|---|---|---|
|admin|全部|创建、运行、复核和批准归档|
|analyst|观测/窗口/频谱设置/幅相/周期复核|导入、配置、运行和提审；归档后端403|
|viewer|全部只读与报告下载|核对时间口径和峰值；写操作后端403|

## 启动与账号

```sh
cp .env.example .env
docker compose up -d --build --wait
docker compose exec -T backend python -m scripts.seed_demo
```

前端 http://localhost:18226 ，后端文档 http://localhost:19226/docs ，PostgreSQL映射17726。账号：admin@beiyu.demo、analyst@beiyu.demo、viewer@beiyu.demo，密码均为 `Signal2026!`。开发JWT密钥应在部署前替换。

恰好frontend/backend/worker/db/redis五服务，全部healthcheck。backend等待PG/Redis健康，worker再等backend完成种子，frontend等待backend。PG、Redis AOF与worker心跳分别命名卷。结束演示执行 `docker compose down -v --remove-orphans`，会删除本项目演示数据。

SEED_DEMO=true首次建表并幂等填充固定ID/自然键，不重复新增、不覆盖用户修改。seed2307生成6链路各480点（共2880点）：BY-01为带轻噪声30/80分钟组合；BY-02另含线性趋势；BY-03有采样间隔空缺但仍保留480个真实点；BY-04时间抖动不规则；BY-05为45/120分钟组合；BY-06为常量失败态示例。种子含六窗口、完成的BY-01双谱研究与人工报告，另含两个多链路对照研究：BY-01…04的共享30分钟周期联合对照（完成、有相位差）和BY-05/06的证据不足示例（明确不给同步结论）。无真实链路资料。

## 六实体与页面

SignalDataset保留原始link_id/time_minutes/jitter_ms；SamplingWindow锁定链路、时间边界和实际点数；SpectralStudy保存去趋势、FFT窗、频率范围和LS网格；SpectralRun经Redis独立worker计算并持久化；PeriodReview记录人工判断与解释边界；Report仅在最新复核accepted后由admin归档，run唯一。

六业务页：观测总览、带时间观测、采样窗口、频谱设置、周期与幅相、周期复核（含操作留痕）。实际原波形、残差、FFT、LS、峰表与联合幅相全部来自后端结果，前端只画数据。原始点先按时间稳定排序，连线只用于阅读，不表示重采样；表格预览30点，算法与图线使用全量窗口点。

### 多链路周期对照（第07页）

历史单链路流程与页面（第05页）完全保留，结果结构、查看方式和报告口径不变；多链路对照是独立的ComparisonStudy/ComparisonRun实体、独立Redis队列（`jitter-spectrum:comparison-jobs`）与独立页面，不写入或改写spectral_runs。

对照只在所选窗口的**共同覆盖时段**内进行，参与窗口须来自同一观测集、不同链路，且每条链路在共同覆盖内至少16个真实点。各链路保留自己的真实采样时刻，缺采样不补0、不插值、不重采样；每条链路在原始观测上按真实时间拟合 `常数(+线性趋势)+sin+cos`。联合谱为各链路去趋势基线SSE加权的浮动均值LS解释比例：`Σ SSE0_k·P_k(f)/Σ SSE0_k`。先在显式等频率网格上找联合局部峰，再以峰所在网格索引的相邻网格线为括号做201点细化并三点二次插值；细化括号只由绝对频率轴决定，设计矩阵仅依赖`(t−共同原点)`。

共享频率需**每条有效链路**在该频率解释比例≥0.20且联合解释比例≥0.30，并在联合峰中按功率降序选取全部链路都达标者。选定后对每条链路在原始观测上联合估计截距、斜率（linear时）、振幅、相位、RMSE与R²。相位约定为 `A*sin(2πf(t−t0)+phi)`、`phi=atan2(cos系数,sin系数)`，其中**t0统一为共同覆盖起点（绝对时间原点）**，而非各窗口首点；因此参与窗口边界错开或所有时间整体平移时，链路间两两相位差保持一致（同一估计频率下达机器精度），同时给出等效时滞 `Δphi/(2πf)` 与振幅比。样本不足、无共同覆盖、常量残差或无满足阈值的共享峰时，仅返回状态与原因，`shared_frequency`为空，不给任何同步结论。相位差只描述该共享频率上的时间关系，不证明故障因果，也不保证其它频率同步。

## 算法、单位与失败态

所有时间用分钟，普通频率f用每分钟周期数，角频率omega=2πf。先对窗口数据排序并拒绝重复时间/非有限值；至少16点。去均值或OLS去线性趋势后，若残差相对均方小到数值常量阈值，则明确失败，不输出假峰。

### 规则FFT单侧PSD

时间差按中位间隔检验近似等间隔（rtol=1e-6、atol=1e-9分钟）。缺点/不规则数据返回FFT available=false，不填0、不静默重采样；LS继续。规则采样率fs=1/dt，Nyquist=fs/2，频率间距=fs/N。研究的最高频率不能超过规则Nyquist；最大搜索周期不得超过实际跨度t_last−t_first。

对去趋势残差y乘Hann或Boxcar窗w，用NumPy rfft。`PSD=|rfft(y*w)|²/(fs*Σw²)`；正频率非Nyquist项加倍，奇数长度末项也加倍，DC和偶数长度Nyquist不加倍。单位为ms²·分钟。全频PSD积分等于`Σ(y*w)²/Σw²`；Boxcar时等于残差均方。全频积分不是用户截取频率区间内的积分。窗函数改变泄漏与幅值，振幅另由联合最小二乘复核，不把PSD峰高直接当作振幅。

FFT频率定义可对照 [NumPy rfft官方说明](https://numpy.org/doc/1.26/reference/generated/numpy.fft.rfft.html)。

### 浮动均值LS周期谱

在明确的[min_frequency,max_frequency]等频率网格上，按实际时间拟合 `c+a*sin(2πf(t−t0))+b*cos(2πf(t−t0))`。每一频率单独拟合常数c，即浮动均值。输入是先去均值/线性趋势后的残差，去趋势方式不隐藏。`P=(SSE0−SSEf)/SSE0`，SSE0为仅常数模型，SSEf为常数+sin+cos模型，输出为无量纲解释方差比例。

不规则时间没有统一Nyquist，本应用只声明用户频率范围、网格密度和观测跨度政策，不把中位间隔当作理论Nyquist。FFT与LS的归一和单位不同，图分开展示，不能强作功率数值等值比较。广义浮动均值方法可对照[原始研究](https://arxiv.org/abs/0901.2573)和[Astropy官方周期谱说明](https://docs.astropy.org/en/stable/timeseries/lombscargle.html)。

### 幅相复核与复现

局部最大峰按功率降序选取，并要求峰间至少1/实际跨度的分离；显示最多五个候选。对前两个LS候选在原始观测上联合拟合，若声明linear则一起拟合截距与线性项。分量定义为 `A*sin(2πf(t−t0)+phi)`，`A=sqrt(a²+b²)`、`phi=atan2(b,a)`，t0为窗口第一条实际观测时间。输出各分量振幅ms、相位rad、截距、斜率、RMSE与R²，附原波形/拟合对照。

相同已排序窗口观测、去趋势/窗/频率参数产生确定性结果，乱序输入排序后结果逐字段相同。重复时间拒绝，不静默去重；不足16点、越覆盖窗口、非有限值、常量残差、过长搜索周期、规则Nyquist越界均明确拒绝或运行failed。失败运行不能提交复核/归档。输入最多6000点、12链路、LS网格32—4000点，f>0且≤10每分钟。没有显著性/FAP或周期因果诊断，接近观测跨度的低频峰尤其需要谨慎。

## 技术与开发

|部分|技术|
|---|---|
|前端|React18.3、TypeScript5.7、Vite6、Nginx1.28|
|后端|Python3.11、FastAPI、SQLAlchemy、PyJWT、NumPy1.26.4|
|持久化|PostgreSQL16，DOUBLE参数与JSON观测/结果|
|后台|Redis7.4 AOF、独立Python worker，同时监听单链路与多链路两个队列，BLAS/OMP/MKL线程均1|

frontend/src含api/stores/types/components/common/hooks/pages/router/utils/constants；backend/src含routes/controllers/services/models/schemas/middlewares/utils/constants/config；backend/scripts含seed，backend/migrations说明初次模型建表。多链路对照算法在backend/src/services/comparison.py，编排与校验在comparison_studies.py/comparison_runs.py。测试、截图、日志、TESTING与verification在批次test-artifacts/gb-2307，源码不混入产物；本仓库verify/提供本地可复跑的纯算法、编排与HTTP端到端脚本（compare_oracle.py、compare_integration.py、compare_e2e.py，宿主装NumPy/SQLAlchemy/FastAPI/httpx后用sqlite即可，不需起Docker）。

后端本地安装requirements.txt，配置DATABASE_URL/REDIS_URL/JWT_SECRET并设置BLAS线程1，在backend执行`uvicorn src.main:app --reload`，另开`python -m src.worker`。前端`npm ci && npm run dev`；开发时将/api同源代理到19226，Docker Nginx已去前缀。React锁只改根包名和根package名，依赖节点原样，Docker用npm ci。

环境：COMPOSE_PROJECT_NAME=jitter-spectrum；FRONTEND_PORT=18226；BACKEND_PORT=19226；DB_PORT=17726；JWT_SECRET；SEED_DEMO。DATABASE_URL/REDIS_URL由Compose传入；OPENBLAS_NUM_THREADS/OMP_NUM_THREADS/MKL_NUM_THREADS固定1。`.env`忽略，`.env.example`供复制。

共享枚举角色/运行状态/去趋势/FFT窗在backend/src/constants/enums.py与frontend/src/constants/enums.ts；角色规则在controllers/auth.py和App，状态由services/runs.py/worker.py更新、Status组件消费；去趋势与窗由schemas/study.py验证、Studies页输入并由preprocessing/fft消费。复核decision在schemas/review.py与前端constants，Reviews页展示。

## 已知边界

两谱不是同一种功率尺度，不能仅凭峰高相互验证。有限跨度、窗泄漏、频率网格、采样模式和趋势预处理都会影响候选；没有置信区间、FAP或因果诊断。单链路幅相以首观测为原点，改变窗口会改变相位，因此不能直接拿单链路相位互比；跨链路比较必须走第07页、以共同覆盖起点为统一原点的对照。多链路对照只拟合单个共享频率，未建模的其它周期分量会影响该频率的估计；有限窗口的频率估计存在约1e-6量级数值地板并经长跨度放大，同频率下的相位差本身仍达机器精度平移不变。无共同覆盖、共同覆盖内某链路不足16点、常量残差或无满足阈值的共享峰时只报原因，不给同步结论。JSON表单导入，无CSV解析器。单worker启动恢复queued/running（含两个队列），无分布式租约；初次SQLAlchemy建表，无生产迁移回滚。Google Fonts使用Noto Sans SC/IBM Plex Mono，不可用时回退。开发密钥和演示账号供本地模拟。

测试脚本algorithm_oracle.py在宿主没有NumPy时会把同一手算oracle经stdin交给已启动backend容器执行；需先up栈，不额外安装宿主依赖。verify/下的compare_oracle.py（48项算法断言，含平移/错开不变性、缺采样、无覆盖、样本不足、弱证据、确定性）、compare_integration.py与compare_e2e.py可在宿主直接复跑，覆盖多链路对照的算法、编排与HTTP权限链路。

MIT License。
