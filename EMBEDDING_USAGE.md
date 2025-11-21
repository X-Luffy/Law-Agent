# Embedding Function 使用情况总结

本文档总结了系统中所有使用 `embedding_model.encode()` 方法的地方。

## 1. 工具选择器 (ToolSelector)

**文件**: `embedding/tool_selector.py`

### 1.1 嵌入工具描述
- **位置**: `embed_tool_descriptions()` 方法
- **用途**: 为所有工具描述生成embedding向量，用于后续的工具选择
- **调用方式**: 
  ```python
  embeddings = self.embedding_model.encode(descriptions)  # 批量编码
  embedding = self.embedding_model.encode(description)   # 单个编码（备用）
  ```
- **使用场景**: 初始化工具选择器时，批量编码所有工具描述

### 1.2 选择工具
- **位置**: `select_tools()` 方法
- **用途**: 将用户查询转换为embedding，与工具描述embedding计算相似度
- **调用方式**: 
  ```python
  query_embedding = self.embedding_model.encode(query_text)
  ```
- **使用场景**: 每次用户查询时，选择最相关的工具

### 1.3 获取工具相似度
- **位置**: `get_tool_similarities()` 方法
- **用途**: 获取所有工具与用户查询的相似度分数
- **调用方式**: 
  ```python
  query_embedding = self.embedding_model.encode(query_text)
  ```
- **使用场景**: 获取所有工具的相似度排名

## 2. 向量数据库 (VectorDatabase)

**文件**: `memory/vector_db.py`

### 2.1 自动检测embedding维度
- **位置**: `__init__()` 方法
- **用途**: 使用测试文本检测embedding的实际维度
- **调用方式**: 
  ```python
  test_embedding = self.embedding_model.encode("test")
  ```
- **使用场景**: 初始化向量数据库时，如果配置的维度为0或None

### 2.2 添加记忆
- **位置**: `add_memory()` 方法
- **用途**: 将记忆内容转换为embedding向量，存储到向量数据库
- **调用方式**: 
  ```python
  embedding = self.embedding_model.encode(content)
  ```
- **使用场景**: 保存对话记忆到长期记忆时

### 2.3 检索记忆
- **位置**: `retrieve_memories()` 方法
- **用途**: 将查询文本转换为embedding向量，用于向量相似度搜索
- **调用方式**: 
  ```python
  query_embedding = self.embedding_model.encode(query)
  ```
- **使用场景**: 从长期记忆中检索相关记忆时

## 3. 上下文精炼器 (ContextRefiner)

**文件**: `context/refiner.py`

### 3.1 提取关键信息点
- **位置**: `_extract_key_points_with_embedding()` 方法
- **用途**: 对往期对话消息进行embedding编码，用于聚类和提取关键信息
- **调用方式**: 
  ```python
  embeddings = self.embedding_model.encode(message_contents)
  ```
- **使用场景**: 精炼往期对话时，提取关键信息点

## 4. 上下文管理器 (ContextManager)

**文件**: `context/manager.py`

### 4.1 精炼上下文
- **位置**: `get_context()` 方法中的精炼逻辑
- **用途**: 对关键信息点进行embedding编码（通过refiner间接调用）
- **调用方式**: 
  ```python
  embeddings = self.refiner.embedding_model.encode(key_points)
  ```
- **使用场景**: 管理上下文时，对关键信息点进行编码

## 5. RAG检索器 (RAGRetriever)

**文件**: `rag/retriever.py`

### 5.1 检索文档
- **位置**: `retrieve()` 方法（通过VectorStore间接调用）
- **用途**: 将查询文本转换为embedding向量，用于向量相似度搜索
- **调用方式**: 
  ```python
  # 通过VectorStore.search()间接调用
  query_embedding = self.embedding_model.encode(query)
  ```
- **使用场景**: 从法律专业信息库中检索相关文档时

## 6. 向量存储 (VectorStore)

**文件**: `memory/vector_store.py` 和相关实现

### 6.1 添加文档
- **位置**: `add_documents()` 方法
- **用途**: 将文档内容转换为embedding向量，存储到向量数据库
- **调用方式**: 
  ```python
  embedding = self.embedding_model.encode(content)
  ```
- **使用场景**: 添加法律文档到知识库时

### 6.2 搜索文档
- **位置**: `search()` 方法
- **用途**: 将查询文本转换为embedding向量，用于向量相似度搜索
- **调用方式**: 
  ```python
  query_embedding = self.embedding_model.encode(query)
  ```
- **使用场景**: 从知识库中搜索相关文档时

## 总结

### Embedding使用场景分类

1. **工具选择** (ToolSelector)
   - 工具描述编码（初始化时）
   - 用户查询编码（每次查询时）

2. **记忆管理** (VectorDatabase)
   - 记忆内容编码（保存记忆时）
   - 查询编码（检索记忆时）

3. **上下文管理** (ContextRefiner, ContextManager)
   - 消息编码（精炼上下文时）
   - 关键信息点编码（提取关键信息时）

4. **RAG检索** (RAGRetriever, VectorStore)
   - 文档编码（添加文档时）
   - 查询编码（检索文档时）

### 调用频率

- **高频调用**: 
  - 工具选择（每次用户查询）
  - 记忆检索（每次用户查询）
  - RAG检索（每次需要检索时）

- **中频调用**:
  - 记忆保存（每次对话后）
  - 上下文精炼（对话历史超过阈值时）

- **低频调用**:
  - 工具描述编码（初始化时）
  - 文档添加（添加新文档时）
  - 维度检测（初始化时）

### 性能考虑

1. **批量编码**: 工具描述编码使用批量编码，提高效率
2. **缓存机制**: 工具描述embedding会被缓存，避免重复编码
3. **超时和重试**: 所有embedding调用都支持超时和重试机制
4. **错误处理**: 所有embedding调用都有错误处理，避免单点失败

