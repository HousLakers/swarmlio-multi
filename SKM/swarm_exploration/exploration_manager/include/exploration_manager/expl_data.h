#ifndef _EXPL_DATA_H_
#define _EXPL_DATA_H_

#include <Eigen/Eigen>
#include <vector>
#include <deque>
#include <bspline/Bspline.h>

using Eigen::Vector3d;
using std::vector;
using std::deque;

namespace fast_planner {
struct FSMData {
  // FSM data
  bool trigger_, have_odom_, static_state_;
  vector<string> state_str_;

  Eigen::Vector3d odom_pos_, odom_vel_;  // odometry state
  Eigen::Quaterniond odom_orient_;
  double odom_yaw_;

  Eigen::Vector3d start_pt_, start_vel_, start_acc_, start_yaw_;  // start state
  vector<Eigen::Vector3d> start_poss;
  bspline::Bspline newest_traj_;

  // Swarm collision avoidance
  bool avoid_collision_, go_back_;

  // T1S1 FSM stagnation recovery telemetry/state.
  struct StagnationSample {
    ros::Time t;
    Eigen::Vector3d pos;
    double speed;
  };
  deque<StagnationSample> sliding_recovery_samples_;
  int sliding_recovery_count_;
  int sliding_recovery_good_evals_;
  bool sliding_recovery_pending_;
  ros::Time sliding_recovery_last_time_;

  bool stagnation_recovery_initialized_;
  int stagnation_recovery_count_;
  ros::Time stagnation_recovery_anchor_time_;
  ros::Time stagnation_recovery_last_time_;
  Eigen::Vector3d stagnation_recovery_anchor_pos_;

  ros::Time fsm_init_time_;
  ros::Time last_check_frontier_time_;
  ros::Time idle_start_time_;

  Eigen::Vector3d start_pos_;

  int sim_drop_count_;  // 丢包模拟: 丢弃消息计数
};

struct FSMParam {
  double replan_thresh1_;
  double replan_thresh2_;
  double replan_thresh3_;
  double replan_time_;  // second

  // Swarm
  double attempt_interval_;   // Min interval of opt attempt
  double pair_opt_interval_;  // Min interval of successful pair opt
  int repeat_send_num_;

  // T1S1 FSM stagnation recovery parameters.
  bool sliding_recovery_enabled_;
  double sliding_recovery_window_;
  double sliding_recovery_displacement_;
  double sliding_recovery_mean_speed_;
  double sliding_recovery_current_speed_;
  int sliding_recovery_good_evals_required_;
  double sliding_recovery_cooldown_;
  int sliding_recovery_max_count_;

  bool stagnation_recovery_enabled_;
  double stagnation_window_;
  double stagnation_displacement_;
  double stagnation_speed_;
  double stagnation_cooldown_;
  int stagnation_max_recoveries_;

  // 20% 丢包鲁棒性: 对称生效协议 + 丢包模拟
  double opt_retry_interval_;  // 待确认提案重传间隔
  double opt_timeout_;         // 待确认提案超时(放弃等待, 靠心跳自愈兜底)
  double sim_drop_rate_;       // 丢包模拟比例 [0,1], 0=不丢包(仅测试用)
};

struct DroneState {
  Eigen::Vector3d pos_;
  Eigen::Vector3d vel_;
  double yaw_;
  double stamp_;                // Stamp of pos,vel,yaw
  double recent_attempt_time_;  // Stamp of latest opt attempt with any drone

  vector<int> grid_ids_;         // Id of grid tour
  double recent_interact_time_;  // Stamp of latest opt with this drone
  bool is_online_;               // 是否在线(心跳超时则 false)
  int offline_miss_count_;       // 连续心跳超时次数(>=2 才判掉线, 防瞬时误报)
};

struct ExplorationData {
  vector<vector<Vector3d>> frontiers_;
  vector<vector<Vector3d>> dead_frontiers_;
  vector<pair<Vector3d, Vector3d>> frontier_boxes_;
  vector<Vector3d> points_;
  vector<Vector3d> averages_;
  vector<Vector3d> views_;
  vector<double> yaws_;
  vector<Vector3d> frontier_tour_;
  vector<vector<Vector3d>> other_tours_;

  vector<int> refined_ids_;
  vector<vector<Vector3d>> n_points_;
  vector<Vector3d> unrefined_points_;
  vector<Vector3d> refined_points_;
  vector<Vector3d> refined_views_;  // points + dir(yaw)
  vector<Vector3d> refined_views1_, refined_views2_;
  vector<Vector3d> refined_tour_;

  Vector3d next_goal_;
  vector<Vector3d> path_next_goal_, kino_path_;
  Vector3d next_pos_;
  double next_yaw_;

  // Goal stickiness: track last selected target to avoid oscillation
  int last_target_id_;

  // viewpoint planning
  // vector<Vector4d> views_;
  vector<Vector3d> views_vis1_, views_vis2_;
  vector<Vector3d> centers_, scales_;

  // Swarm, other drones' state
  vector<DroneState> swarm_state_;
  vector<double> pair_opt_stamps_, pair_opt_res_stamps_;
  vector<int> ego_ids_, other_ids_;
  double pair_opt_stamp_;
  bool reallocated_, wait_response_;

  // 对称生效 pair-opt 协议(20% 丢包鲁棒性): 提案备份/重传/幂等应答/统计
  vector<int> pre_opt_ego_ids_, pre_opt_other_ids_;  // 提案前分配(被拒绝时回滚)
  double last_opt_send_time_;                        // 提案发送/最近重传时刻
  int pair_opt_target_id_;                           // 待确认提案的目标机 id
  vector<int> last_opt_response_status_;             // 对每个来源已处理提案的应答状态(幂等重答)
  int pair_opt_sent_count_;                          // 提案发送计数(统计)
  int opt_reverted_count_;                           // 提案被拒回滚计数(统计)
  int conflict_resolved_count_;                      // 心跳冲突自愈释放的网格数(统计)

  // Coverage planning
  vector<Vector3d> grid_tour_, grid_tour2_;
  // int prev_first_id_;
  vector<int> last_grid_ids_;

  int plan_num_;
};

struct ExplorationParam {
  // params
  bool refine_local_;
  int refined_num_;
  double refined_radius_;
  int top_view_num_;
  double max_decay_;
  string tsp_dir_;   // resource dir of tsp solver
  string mtsp_dir_;  // resource dir of tsp solver
  double relax_time_;
  int init_plan_num_;

  // Swarm
  int drone_num_;
  int drone_id_;

  // 负载均衡(与队友参数化形式一致, 默认 MINSUM/0.75)
  string mtsp_objective_;  // MINSUM | MINMAX
  double capacity_factor_; // 单机容量系数 [0,1]
};

}  // namespace fast_planner

#endif