# 知识库导航索引

> 本文件为 knowledge/ 目录的精简导航。详细内容按需从对应路径读取。
> 知识库最近更新: 2026-04-05（L3/L4/L5 模板升级 + 全量重构 + 三层目录对齐）
> 10 个业务域: activity / app / award / money / voucher / score / user / interaction / operation / page

## 顶层文件

| 文件 | 说明 |
|------|------|
| knowledge/README.md | 知识库使用说明 |
| knowledge/version.md | 版本信息与完成状态 |
| knowledge/L1_repo_metadata.md | 仓库基本信息、目录骨架、构建方式、核心依赖 |
| knowledge/L2_architecture_metadata.md | 架构分层、进程模型、子应用清单、DI、多租户、业务域依赖图 |

---

## 模块索引 (L3)

> 导航入口: `knowledge/L3_modules/_index.md` (模块总览)
> 术语表: `knowledge/L3_modules/_glossary.md`
> 文档模板: `knowledge/L3_modules/_template.md`
> 质量报告: `knowledge/L3_modules/_quality_report.md`
>
> **L3 vs L5 分工**: L3 = 理解与修改模块（职责/流程/状态/接口/实体/依赖/Wire 注入清单）；L5 = 调用模块（纯接口方法签名，不含依赖信息）。
> **14 子目录**: 10 业务域 + framework + infra + crosscutting + external

### 独立业务子应用 (internal/app/) — 8 个

| 模块 | 用途 | 路径 |
|------|------|------|
| shortlink | 短链接生成与跳转 | knowledge/L3_modules/app/shortlink.md |
| meetup | 线下线上会议活动管理 | knowledge/L3_modules/app/meetup.md |
| membershipinvite | 多牌照邀请注册活动 | knowledge/L3_modules/app/membershipinvite.md |
| hktransferingift2026 | HK 2026转仓礼活动 | knowledge/L3_modules/app/hktransferingift2026.md |
| teamgame2026 | 2026版组队交易竞赛 | knowledge/L3_modules/app/teamgame2026.md |
| scoredraw | 虎币抽奖活动 | knowledge/L3_modules/app/scoredraw.md |
| earningseason | 财报季活动 | knowledge/L3_modules/app/earningseason.md |
| fixedvote | 定投活动 | knowledge/L3_modules/app/fixedvote.md |

### 共享服务 (internal/services/) — 80+ 个

#### 活动管理 (7)

| 模块 | 详细文件 |
|------|----------|
| activity | knowledge/L3_modules/activity/activity.md |
| activityboard | knowledge/L3_modules/activity/activityboard.md |
| activitycore | knowledge/L3_modules/activity/activitycore.md |
| activityentry | knowledge/L3_modules/activity/activityentry.md |
| activitytask | knowledge/L3_modules/activity/activitytask.md |
| activitytraffic | knowledge/L3_modules/activity/activitytraffic.md |
| oldactivity | knowledge/L3_modules/activity/oldactivity.md |

#### 奖品与发奖 (7)

| 模块 | 详细文件 |
|------|----------|
| award | knowledge/L3_modules/award/award.md |
| awardactivate | knowledge/L3_modules/award/awardactivate.md |
| directreward | knowledge/L3_modules/award/directreward.md |
| stockaward | knowledge/L3_modules/award/stockaward.md |
| rewardcenter | knowledge/L3_modules/award/rewardcenter.md |
| rewardcenterv3 | knowledge/L3_modules/award/rewardcenterv3.md |
| rewardv2 | knowledge/L3_modules/award/rewardv2.md |

#### 资金与预算 (3)

| 模块 | 详细文件 |
|------|----------|
| money | knowledge/L3_modules/money/money.md |
| ledger | knowledge/L3_modules/money/ledger.md |
| budget | knowledge/L3_modules/money/budget.md |

#### 券类 (11)

| 模块 | 详细文件 |
|------|----------|
| coupon | knowledge/L3_modules/voucher/coupon.md |
| exchangevoucher | knowledge/L3_modules/voucher/exchangevoucher.md |
| freecard | knowledge/L3_modules/voucher/freecard.md |
| idlecashcoupon | knowledge/L3_modules/voucher/idlecashcoupon.md |
| ipovoucher | knowledge/L3_modules/voucher/ipovoucher.md |
| redeemvoucher | knowledge/L3_modules/voucher/redeemvoucher.md |
| stockvoucher | knowledge/L3_modules/voucher/stockvoucher.md |
| videovoucher | knowledge/L3_modules/voucher/videovoucher.md |
| yieldvoucher | knowledge/L3_modules/voucher/yieldvoucher.md |
| forexcard | knowledge/L3_modules/voucher/forexcard.md |
| fundholdinggaincard | knowledge/L3_modules/voucher/fundholdinggaincard.md |

#### 积分与虎币 (3)

| 模块 | 详细文件 |
|------|----------|
| score | knowledge/L3_modules/score/score_score.md |
| scorev2 | knowledge/L3_modules/score/score_scorev2.md |
| tigercoin | knowledge/L3_modules/score/score_tigercoin.md |

#### 用户与会员 (5)

| 模块 | 详细文件 |
|------|----------|
| user | knowledge/L3_modules/user/user.md |
| userv2 | knowledge/L3_modules/user/userv2.md |
| invitation | knowledge/L3_modules/user/invitation.md |
| invitefriend | knowledge/L3_modules/user/invitefriend.md |
| member | knowledge/L3_modules/user/member.md |

#### 互动玩法 (7)

| 模块 | 详细文件 |
|------|----------|
| assist | knowledge/L3_modules/interaction/svc_interaction_assist.md |
| assistance | knowledge/L3_modules/interaction/interaction_assistance.md |
| assistdebitcard | knowledge/L3_modules/interaction/interaction_assistdebitcard.md |
| quiz | knowledge/L3_modules/interaction/interaction_quiz.md |
| quizzes | knowledge/L3_modules/interaction/quizzes.md |
| stockgame | knowledge/L3_modules/interaction/stockgame.md |
| lottery | knowledge/L3_modules/interaction/interaction_lottery.md |

#### 运营支撑 (11)

| 模块 | 详细文件 |
|------|----------|
| delivery | knowledge/L3_modules/operation/delivery.md |
| operaplat | knowledge/L3_modules/operation/operaplat.md |
| whitelist | knowledge/L3_modules/operation/whitelist.md |
| commissiongroupcard | knowledge/L3_modules/operation/commissiongroupcard.md |
| feishu | knowledge/L3_modules/operation/operation_feishu.md |
| handover | knowledge/L3_modules/operation/handover.md |
| quote | knowledge/L3_modules/operation/svc_operation_quote.md |
| marketability | knowledge/L3_modules/operation/marketability.md |
| precisemarket | knowledge/L3_modules/operation/precisemarket.md |
| symbolwhitelist | knowledge/L3_modules/operation/symbolwhitelist.md |
| campaigntask | knowledge/L3_modules/operation/campaigntask.md |

#### 页面与展示 (5)

| 模块 | 详细文件 |
|------|----------|
| landingpage | knowledge/L3_modules/page/landingpage.md |
| h5page | knowledge/L3_modules/page/h5page.md |
| h5pagemoudle | knowledge/L3_modules/page/h5pagemoudle.md |
| displaycard | knowledge/L3_modules/page/displaycard.md |
| avatarframe | knowledge/L3_modules/page/avatarframe.md |

#### 框架与架构 (5)

| 模块 | 详细文件 |
|------|----------|
| consumer | knowledge/L3_modules/framework/consumer.md |
| mq | knowledge/L3_modules/framework/mq.md |
| transfer | knowledge/L3_modules/framework/transfer.md |
| grpc | knowledge/L3_modules/framework/grpc.md |
| schedule | knowledge/L3_modules/framework/schedule.md |

#### 基础设施与工具 (18)

| 模块 | 详细文件 |
|------|----------|
| asyncpush | knowledge/L3_modules/infra/asyncpush.md |
| authmqtrans | knowledge/L3_modules/infra/authmqtrans.md |
| delaymessage | knowledge/L3_modules/infra/infra_delaymessage.md |
| gcs | knowledge/L3_modules/infra/infra_gcs.md |
| clientupload | knowledge/L3_modules/infra/clientupload.md |
| s2supload | knowledge/L3_modules/infra/svc_infra_s2supload.md |
| crm | knowledge/L3_modules/infra/infra_crm.md |
| datawarehouse | knowledge/L3_modules/infra/infra_datawarehouse.md |
| tradeinfo | knowledge/L3_modules/infra/svc_infra_tradeinfo.md |
| camponent | knowledge/L3_modules/infra/camponent.md |
| choice | knowledge/L3_modules/infra/choice.md |
| guide | knowledge/L3_modules/infra/infra_guide.md |
| verify | knowledge/L3_modules/infra/svc_infra_verify.md |
| validation | knowledge/L3_modules/infra/svc_infra_validation.md |
| base | knowledge/L3_modules/infra/base.md |
| pkg | knowledge/L3_modules/infra/infra_pkg.md |
| utils | knowledge/L3_modules/infra/svc_infra_utils.md |
| ruleengine_utils | knowledge/L3_modules/infra/ruleengine_utils.md |

### 横切关注点 (4)

| 模块 | 详细文件 |
|------|----------|
| ruleengine | knowledge/L3_modules/crosscutting/ruleengine.md |
| riskengine | knowledge/L3_modules/crosscutting/riskengine.md |
| monitor | knowledge/L3_modules/crosscutting/monitor.md |
| reconciliation | knowledge/L3_modules/crosscutting/reconciliation.md |

### 外部集成 (internal/secondpart/) — 46 个

#### 认证与用户 (7)

| 模块 | 详细文件 |
|------|----------|
| auth | knowledge/L3_modules/external/auth.md |
| innerauth | knowledge/L3_modules/external/innerauth.md |
| userprofile | knowledge/L3_modules/external/userprofile.md |
| user_report | knowledge/L3_modules/external/user_report.md |
| user_report_ib | knowledge/L3_modules/external/user_report_ib.md |
| crm | knowledge/L3_modules/external/crm.md |
| countrycode | knowledge/L3_modules/external/countrycode.md |

#### 交易与金融 (13)

| 模块 | 详细文件 |
|------|----------|
| trade | knowledge/L3_modules/external/trade.md |
| tradingmate | knowledge/L3_modules/external/tradingmate.md |
| brokerage | knowledge/L3_modules/external/brokerage.md |
| commissiongroup | knowledge/L3_modules/external/commissiongroup.md |
| ledger | knowledge/L3_modules/external/ledger.md |
| ledgeraccess | knowledge/L3_modules/external/ledgeraccess.md |
| budget | knowledge/L3_modules/external/budget.md |
| omnibusPay | knowledge/L3_modules/external/omnibuspay.md |
| bos | knowledge/L3_modules/external/bos.md |
| bos_http | knowledge/L3_modules/external/bos_http.md |
| dasp | knowledge/L3_modules/external/dasp.md |
| fineex | knowledge/L3_modules/external/fineex.md |
| autoinvestment | knowledge/L3_modules/external/autoinvestment.md |

#### 消息与基础设施 (12)

| 模块 | 详细文件 |
|------|----------|
| message | knowledge/L3_modules/external/message.md |
| firebase | knowledge/L3_modules/external/firebase.md |
| feishu | knowledge/L3_modules/external/feishu.md |
| feishu_transfer | knowledge/L3_modules/external/feishu_transfer.md |
| nacos | knowledge/L3_modules/external/nacos.md |
| apollo | knowledge/L3_modules/external/apollo.md |
| discovery | knowledge/L3_modules/external/discovery.md |
| meta | knowledge/L3_modules/external/meta.md |
| afupload | knowledge/L3_modules/external/afupload.md |
| ftp | knowledge/L3_modules/external/ftp.md |
| sftp | knowledge/L3_modules/external/sftp.md |
| exchangerate | knowledge/L3_modules/external/exchangerate.md |

#### 内容与其他 (14)

| 模块 | 详细文件 |
|------|----------|
| community | knowledge/L3_modules/external/community.md |
| communityintra | knowledge/L3_modules/external/communityintra.md |
| college | knowledge/L3_modules/external/college.md |
| stock_news | knowledge/L3_modules/external/stock_news.md |
| hq | knowledge/L3_modules/external/hq.md |
| quote | knowledge/L3_modules/external/quote.md |
| datawarehouse | knowledge/L3_modules/external/datawarehouse.md |
| riskcontrol | knowledge/L3_modules/external/riskcontrol.md |
| taskrule | knowledge/L3_modules/external/taskrule.md |
| ue | knowledge/L3_modules/external/ue.md |
| giftano | knowledge/L3_modules/external/giftano.md |
| jtexpress | knowledge/L3_modules/external/jtexpress.md |
| cg | knowledge/L3_modules/external/cg.md |
| cg_server | knowledge/L3_modules/external/cg_server.md |

---

## 数据模型索引 (L4)

> 导航入口: `knowledge/L4_data_model/_index.md` (~258 文件, 每文件一个表, 按域分组)
> 模板: `knowledge/L4_data_model/_template.md`

| 域 | 子目录 | 文件数 | 说明 |
|----|--------|--------|------|
| 活动相关 | knowledge/L4_data_model/activity/ | 55 + _index | 活动配置/报名/任务/看板等表 |
| 奖品相关 | knowledge/L4_data_model/award/ | 27 + _index | 奖品/批次/日志/配置等表 |
| 资金与预算 | knowledge/L4_data_model/money/ | 16 + _index | 现金奖励/预算/汇率/转账等表 |
| 券类 | knowledge/L4_data_model/voucher/ | 26 + _index | 各类券的记录表 |
| 积分与虎币 | knowledge/L4_data_model/score/ | 36 + _index | 积分/虎币/签到等表 |
| 用户与会员 | knowledge/L4_data_model/user/ | 36 + _index | 用户域表 + 会员等级/权益等表 |
| 互动玩法 | knowledge/L4_data_model/interaction/ | 25 + _index | 助力/答题/炒股/抽奖等表 |
| 运营支撑 | knowledge/L4_data_model/operation/ | 33 + _index | 发货/精准营销/白名单等表 |
| 页面与展示 | knowledge/L4_data_model/page/ | 3 + _index | 落地页规则/抽奖等表 |
| 子应用私有表 | knowledge/L4_data_model/app/ | 49 + _index | 6 子目录: meetup(12)/membershipinvite(9)/shortlink(2)/scoredraw(1)/hktransferingift2026(1)/teamgame2026(16) + common_repo.md |

---

## 服务契约索引 (L5)

> 导航入口: `knowledge/L5_service_contracts/_index.md` (~99 个服务, 每文件一个 service)
> 模板: `knowledge/L5_service_contracts/_template.md`
> 事件目录: `knowledge/L5_service_contracts/event_catalog.md` (Kafka Topic 全量索引)
> 外部集成文档统一在 L3/external（L5 不再单独维护外部集成契约）

| 域 | 子目录 | 文件数 | 说明 |
|----|--------|--------|------|
| 活动管理 | knowledge/L5_service_contracts/activity/ | 7 + _index | activity/activityboard/activitycore/activityentry/activitytask/activitytraffic/oldactivity |
| 奖品与发奖 | knowledge/L5_service_contracts/award/ | 8 + _index | award/awardactivate/awardexpose/directreward/rewardcenter/rewardcenterv3/rewardv2/stockaward |
| 资金与预算 | knowledge/L5_service_contracts/money/ | 9 + _index | money/money_deleter/ledger/ledgerinner/ledger_provider/budget/exchangerate/rebate_blacklist/feishu_event_transfer |
| 券类 | knowledge/L5_service_contracts/voucher/ | 11 + _index | coupon/exchangevoucher/freecard/fundholdinggaincard/idlecashcoupon/ipovoucher/redeemvoucher/stockvoucher/videovoucher/yieldvoucher/forexcard |
| 积分与虎币 | knowledge/L5_service_contracts/score/ | 3 + _index | score/scorev2/tigercoin |
| 用户与会员 | knowledge/L5_service_contracts/user/ | 4 + _index | user/userv2/invitefriend/member |
| 互动玩法 | knowledge/L5_service_contracts/interaction/ | 7 + _index | assist/assistance/assistdebitcard/quiz/quizzes/stockgame/lottery |
| 运营工具 | knowledge/L5_service_contracts/operation/ | 7 + _index | delivery/operaplat/whitelist/commissiongroupcard/feishu/handover/quote |
| 页面与展示 | knowledge/L5_service_contracts/page/ | 4 + _index | landingpage/h5page/h5pagemoudle/displaycard |
| 基础设施 | knowledge/L5_service_contracts/infra/ | 4 + _index | asyncpush/camponent/clientupload/validation |

---

## 查阅路径

Requirements → Design 推荐查阅顺序：

```
L3 _index.md → 定位涉及的模块
    ↓
L3 <domain>/<module>.md → 了解模块职责、接口、依赖、Wire 注入
    ↓
L4 _index.md → 评估数据模型影响
    ↓
L5 _index.md → 评估 service 能力（方法签名）
    ↓
L5 event_catalog.md → 确认 Kafka 事件（如涉及消息消费/生产）
```
