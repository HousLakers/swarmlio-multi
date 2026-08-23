# SESSION_HANDOFF

## 当前目标

在不进入 smoke 的前提下，完成 2-UAV compute-overlay diagnostic preflight 的资源归因，
解决 16-GB 主机上的运行期内存/换页问题后，再由 lead 单独审核是否签发新的一次性
`stage: preflight` package。

## 已完成事项

- single 公共 compute overlay 已提交：`8c8ddf2add3f7b3ce4f9943583fd945f16b1bd91`，branch `main`。
- 提交恰含 clean XML bundle、`map_ros.cpp` bundle 和 overlay manifest 三个文件；未 push、未 apply。
- multi 已同步 single identity、overlay manifest identity、0.10 m SDF resolution、2.0 sim s full-map cadence
  及资源合同；静态检查已达 55/55。
- runner/preflight self-test、source hash 15/15、overlay verify/check 21/21、multi/single `git diff --check`
  均通过。
- package `be77efb9fe8689b30a54ed83183e3dda30e3e2ad923aac534389288f16eb0d26` 已消费；不得复用。

## 源码与配置 hash

- single commit：`8c8ddf2add3f7b3ce4f9943583fd945f16b1bd91`
- platform commit：`57c1f34a607b834915f9aa4a4a6b301ecc5a4ffc`
- overlay manifest：`68ceb54faa24f4cc97396634bfc3d611f8e40a6db89999d3cbabc112092ccf62`
- XML bundle：`6739a77cc56bcf91a9525a0ea4b6932b40c1994cb485e437cbed9e587072d227`
- `map_ros.cpp` bundle：`fc23045c16e2f81aa9110a0ede8b2161e50805303a3a361bccfd1609f51e70ae`
- multi manifest：`5cc07755cb46cfb13fda34fa96b9e528766340541c8eb919f62f7a000381e3c5`
- static config：`a0fb9077b67d48cf30ed233a886954966e57df331c73c3f8f2ffa6958b44faed`
- source-hash manifest：`b275c3e06238b9e7a00653bd3b2439e893b47d947b7f085c64fa3974fb25c99a`

## 最新实验

`results/RUN-20260821T202125Z-2uav-preflight/`，diagnostic preflight，失败状态：
`PREFLIGHT_FAILED_RESOURCE_GATE_SWAP`。

- static：55/55；workspace probe：3/3。
- 启动资源门：通过，load1=2.01，MemAvailable=13.63 GB。
- 运行资源门：失败，load1=3.49，MemAvailable=6.88 GB。
- swap-in：29491→29619，增加 128；swap-out 未增加。
- resource profile：17 samples；Gazebo RSS max≈5.17 GB，RACER RSS max≈1.75 GB，本轮无有效 RT sample。
- final metrics timeout、final safety=false；失败发生在 running gate，栈已清理，无 ACTIVE lifecycle/残留进程。

## 已确认事实

- 该失败是资源/基础设施门按设计 fail-closed，不是源码回归或 occupancy 合同失败。
- 0.10 m overlay 已降低地图体素规模，但当前双机全栈仍使系统 MemAvailable 从 13.63 GB 降到 6.88 GB 并触发换页。
- 不能通过降低 `resource_running_mem_available_gib`、忽略 swap delta、放宽 freshness 或伪造 RT 来获得通过。
- 16-GB 主机当前没有足够余量证明双机稳定运行，更不能据此扩展到 3/4 UAV。

## 未解决问题

- 内存峰值和换页来源尚未拆分到具体可治理组件；需要在不改变感知/安全语义的前提下减少峰值或增加主机余量。
- 运行期 resource profile 没有有效连续 RT 样本，compute baseline 的 RT≥0.5 目标尚未验证。
- 当前没有有效 approval package；最近 package 已消费。

## 下一步唯一动作

由 lead/low-level-implementation 形成并验证一个最小资源治理方案：优先评估增加物理内存/关闭外部竞争负载，
其次评估不改变安全语义的进程/地图负载拆分；保持启动 MemAvailable≥8 GiB、运行 MemAvailable≥3 GiB、
swap-in/out 不增长的 fail-closed 门。完成静态/离线资源证据后，交回 lead 再决定是否签发新的一次性 preflight package。

## 禁止重复的工作

- 不得复用 package `be77efb9fe8689b30a54ed83183e3dda30e3e2ad923aac534389288f16eb0d26` 或其 runroot。
- 不得同包重试、直接进入 smoke、运行长跑、手工 goal、3/4-UAV 或参数搜索。
- 不得降低资源门、忽略 swap、修改 freshness/occupancy/安全合同来掩盖资源不足。
- 不得修改源码、manifest、identity、approval package 或 receipt 后继续实验，除非 lead 另行签发明确任务。
- 不得覆盖旧 runroot、提交原始大日志、push、apply overlay 或启动 ROS/Gazebo。

handoff_status: BLOCKED
handoff_model: low-level-implementation
handoff_command:
基于本文件和 RUN-20260821T202125Z-2uav-preflight 资源证据，提出最小内存治理任务并完成离线验证；
不得启动实验、复用旧 package/runroot、降低资源门或创建 approval package。
