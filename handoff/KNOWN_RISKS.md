# Known Risks

- namespace/topic 串线；
- telemetry 生命周期不一致；
- 异步共享地图导致重复覆盖或分配滞后；
- 一架机冻结拖停整个 fleet；
- 机间最小距离和接触没有进入硬门；
- CPU/内存竞争造成仿真时间或日志中断。
