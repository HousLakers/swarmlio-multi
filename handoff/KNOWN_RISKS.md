# Known Risks

- namespace/topic 串线；
- telemetry 生命周期不一致；
- 异步共享地图导致重复覆盖或分配滞后；
- 一架机冻结拖停整个 fleet；
- 机间最小距离和接触没有进入硬门；
- CPU/内存竞争造成仿真时间或日志中断。
- 20 m 全向节点长测出现 6 次随后恢复的 1 s ACK timeout；多机必须逐机记录，且由
  Sol 在运行前决定它是硬停止还是满足明确条件后的 recovered event；
- 单机功能长测由用户早停，缺少最终 scorer metrics，不是 10,800 s endurance PASS；
- overlay 只冻结单节点源码/config，不提供 namespace、vehicle ID、端口、launch、
  fleet scorer 或多机停止语义；
- 20 m 视距相对 20×20 m 地图很长，探索完成后可能长期驻留；completion 与 freeze
  必须通过 planner 状态、coverage、trajectory 和 odometry 联合判定；
- 两机若共享 TF child frame、MAVLink system ID、ROS topic 或结果目录，会产生看似
  正常但不可归属的伪 fleet 数据；
- overlay hash 正确但未重编译时，运行二进制可能仍是旧配置。
- Gazebo 中另一架 iris 的 LiDAR 机体回波可能进入共享地图并覆盖停留 UAV 的起点；当前仅为
  待诊断假设，必须用近机点计数证明后才能实施紧致机体包络剔除。
- `/planning/bspline_N` 是事件型轨迹下发，不可按固定 5 s 连续心跳监管；同时必须保留
  PositionCommand/ACK 连续 freshness 和每机实际进入 command 链的最终有效性门。
- 双机 headless RT factor 已观测约 0.306–0.339，会放大 wall-time watchdog 与规划负载；
  不得以统一放宽 freshness/ACK 阈值掩盖。
