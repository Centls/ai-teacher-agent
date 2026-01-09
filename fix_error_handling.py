#!/usr/bin/env python
"""
修复 server.py 中的错误处理，使其能够区分后端错误和模型 API 错误
"""

def fix_server_error_handling():
    # 读取文件
    with open('src/server.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # 找到需要替换的行（第155-159行，索引从0开始所以是154-158）
    # 原始代码:
    #            except Exception as e:
    #                print(f"Stream Error: {e}")
    #                import traceback
    #                traceback.print_exc()
    #                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    # 新的错误处理代码
    new_error_handling = '''            except Exception as e:
                print(f"Stream Error: {e}")
                import traceback
                traceback.print_exc()

                # 增强错误分类和详细信息
                error_type = "backend_error"
                error_detail = str(e)
                user_message = "后端处理错误，请查看日志"

                # 检测 OpenAI/阿里云 API 错误
                if "openai" in str(type(e).__module__).lower():
                    error_type = "llm_api_error"

                    # 解析具体错误类型
                    if "BadRequestError" in str(type(e).__name__):
                        error_type = "llm_bad_request"

                        # 检查是否是欠费
                        if "Arrearage" in str(e) or "overdue" in str(e).lower():
                            user_message = "⚠️ 阿里云账户欠费，请充值后重试"
                            error_detail = "阿里云百炼账户余额不足或欠费，请访问 https://home.console.aliyun.com/ 充值"
                        # 检查是否是无效模型
                        elif "model" in str(e).lower() and "not found" in str(e).lower():
                            user_message = "❌ 模型名称错误，请检查 .env 配置"
                            error_detail = f"指定的模型不存在或无权访问: {str(e)}"
                        # 检查是否是 API Key 错误
                        elif "api" in str(e).lower() and ("key" in str(e).lower() or "auth" in str(e).lower()):
                            user_message = "🔑 API Key 无效，请检查 .env 配置"
                            error_detail = "阿里云 API Key 无效或已过期"
                        else:
                            user_message = f"🌐 模型 API 请求失败: {str(e)[:100]}"

                    elif "AuthenticationError" in str(type(e).__name__):
                        error_type = "llm_auth_error"
                        user_message = "🔑 API Key 认证失败，请检查 .env 中的 OPENAI_API_KEY"
                        error_detail = "API Key 无效或已过期"

                    elif "RateLimitError" in str(type(e).__name__):
                        error_type = "llm_rate_limit"
                        user_message = "⏱️ API 调用频率超限，请稍后重试"
                        error_detail = "模型 API 请求频率超过限制"

                    elif "APIConnectionError" in str(type(e).__name__):
                        error_type = "llm_connection_error"
                        user_message = "🌐 无法连接到模型 API，请检查网络"
                        error_detail = "网络连接失败或 API 服务不可用"

                # 检测其他常见错误
                elif "ChromaDB" in str(e) or "chroma" in str(e).lower():
                    error_type = "vector_db_error"
                    user_message = "📚 知识库错误，请检查向量数据库"
                    error_detail = f"ChromaDB 错误: {str(e)}"

                elif "DuckDuckGo" in str(e) or "search" in str(e).lower():
                    error_type = "web_search_error"
                    user_message = "🔍 Web 搜索失败，将使用知识库回答"
                    error_detail = f"搜索引擎错误: {str(e)}"

                # 返回详细错误信息
                yield f"data: {json.dumps({
                    'type': 'error',
                    'error_type': error_type,
                    'message': user_message,
                    'detail': error_detail,
                    'technical_info': str(e)
                }, ensure_ascii=False)}\\n\\n"
'''

    # 替换第155-159行（索引154-158）
    new_lines = lines[:154] + [new_error_handling + '\n'] + lines[159:]

    # 写回文件
    with open('src/server.py', 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

    print("✅ 成功修复 src/server.py 的错误处理")
    print("现在错误信息会更详细，可以区分:")
    print("  - 阿里云账户欠费")
    print("  - 模型名称错误")
    print("  - API Key 无效")
    print("  - 网络连接失败")
    print("  - 知识库错误")
    print("  - Web 搜索失败")

if __name__ == "__main__":
    fix_server_error_handling()
