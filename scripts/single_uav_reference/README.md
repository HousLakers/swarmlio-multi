# Single-UAV Reference Scripts

这些文件从 `/home/houslakers/auto_tune_racer/swarmlio-single` 原样复制，作为多机节点能力迁移和对照参考。

它们当前不属于多机执行白名单，不得直接用于 2-UAV 实验。尤其是 `run_e2l_le8i_overnight_randomized_3arm_8x600.sh` 和单机 patch installer 不得由 DeepSeek 自动调用。

迁移原则：

1. 先比较本目录副本与单机源文件 hash；
2. 先完成多机 namespace、launch、telemetry 和 fleet metrics 适配；
3. 任何改动必须由 terra 写入 diff，并由 sol 审核；
4. 多机 manifest 只能引用经过审核的多机 wrapper，不直接引用这里的单机长批脚本。

来源与指纹见 `SOURCE_MANIFEST.sha256`。
