## ADDED Requirements

### Requirement: Video download
系统 SHALL 下载视频文件到本地 `data/media/{sec_user_id}/videos/{aweme_id}.mp4`。

#### Scenario: Download video
- **WHEN** 提交视频下载任务
- **THEN** 从作品数据中提取视频 URL，下载到对应目录，更新 media_files 表状态为 completed

#### Scenario: Skip existing download
- **WHEN** 目标文件已存在且 media_files 记录为 completed
- **THEN** 跳过下载

### Requirement: Image download
系统 SHALL 下载图文作品的所有图片到本地 `data/media/{sec_user_id}/notes/{aweme_id}/`。

#### Scenario: Download note images
- **WHEN** 提交图文下载任务
- **THEN** 从作品数据中提取所有图片 URL，按序号命名下载（1.jpg, 2.jpg...），更新 media_files 表

### Requirement: Download status tracking
系统 SHALL 在 media_files 表追踪每个媒体文件的下载状态（pending/downloading/completed/failed）。

#### Scenario: Failed download retry
- **WHEN** 下载失败且 retry_count < 3
- **THEN** 标记为 failed，后续可重试

#### Scenario: Download progress query
- **WHEN** 查询某作品的媒体下载状态
- **THEN** 返回所有关联 media_files 记录及其状态
