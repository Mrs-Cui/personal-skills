# ES 操作单元测试指南

## Mock 层级选择

| 场景 | 推荐方案 | 原因 |
|------|---------|------|
| **成功场景** | httptest mock HTTP 响应 | 验证完整请求/响应流程 |
| **错误场景** | mockey mock 数据访问层方法 | 避免 ES 客户端内部 panic |
| **查询构建验证** | httptest + 捕获请求体 | 检查发送的查询内容 |

## httptest Mock ES 服务器（成功场景）

```go
// 1. 创建 mock 服务器
server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
    w.Header().Set("Content-Type", "application/json")
    w.WriteHeader(tt.mockEsStatusCode)
    w.Write([]byte(tt.mockEsResponse))
}))
defer server.Close()

// 2. 创建 ES 客户端（必须禁用 Sniff 和 Healthcheck）
esClient, err := elastic.NewClient(
    elastic.SetURL(server.URL),
    elastic.SetSniff(false),       // 禁用节点嗅探
    elastic.SetHealthcheck(false), // 禁用健康检查
)

// 3. 注入到被测服务
searchES := &esrepo.SearchES{Client: &xes.ES{Client: esClient}}
s := &TaskSrv{SearchES: searchES}
```

### 捕获请求体验证查询构建

```go
var capturedRequest []byte
server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
    capturedRequest, _ = io.ReadAll(r.Body)
    w.Header().Set("Content-Type", "application/json")
    w.WriteHeader(200)
    w.Write([]byte(`{"took":1,"hits":{"total":{"value":0},"hits":[]}}`))
}))
defer server.Close()

// 执行测试后验证
requestStr := string(capturedRequest)
if !strings.Contains(requestStr, "expectedField") {
    t.Errorf("查询未包含预期字段")
}
```

## mockey Mock 数据访问层（错误场景）

httptest 模拟 HTTP 500 时 ES 客户端可能 panic，错误场景用 mockey 直接 mock：

```go
searchES := &esrepo.SearchES{}
mocker := mockey.Mock((*esrepo.SearchES).DistinctUuidArray).To(
    func(_ *esrepo.SearchES, ctx context.Context, indices []string, filter *xes.EsSearch) ([]string, int, error) {
        return nil, 0, errors.New("ES cluster unavailable")
    },
).Build()
defer mocker.UnPatch()

s := &TaskSrv{SearchES: searchES}
// 执行测试，验证错误处理逻辑...
```

## ES 响应 JSON 模板

### 正常返回

```json
{
    "took": 1, "timed_out": false,
    "_shards": {"total": 1, "successful": 1, "skipped": 0, "failed": 0},
    "hits": {
        "total": {"value": 2, "relation": "eq"},
        "max_score": 1.0,
        "hits": [
            {"_index": "index_name", "_id": "1", "_score": 1.0, "_source": {"uuid": "1001"}},
            {"_index": "index_name", "_id": "2", "_score": 1.0, "_source": {"uuid": "1002"}}
        ]
    },
    "aggregations": {"uuids": {"value": 2}}
}
```

### 空结果

```json
{
    "took": 1, "timed_out": false,
    "_shards": {"total": 1, "successful": 1, "skipped": 0, "failed": 0},
    "hits": {"total": {"value": 0, "relation": "eq"}, "max_score": null, "hits": []},
    "aggregations": {"uuids": {"value": 0}}
}
```

### 错误响应

```json
{
    "error": {
        "root_cause": [{"type": "index_not_found_exception", "reason": "no such index"}],
        "type": "index_not_found_exception", "reason": "no such index"
    },
    "status": 404
}
```
