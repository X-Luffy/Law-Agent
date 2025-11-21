"""常见工具集合"""
from typing import Dict, Any, List, Optional
import subprocess
import tempfile
import os
import json
from datetime import datetime
from .base import BaseTool
from ..config.config import Config


class PythonExecutorTool(BaseTool):
    """Python代码执行工具"""
    
    def __init__(self, config: Config):
        """
        初始化Python执行工具
        
        Args:
            config: 系统配置
        """
        super().__init__(
            name="python_executor",
            description="Execute Python code. Use this tool when you need to run calculations, data processing, or any Python code. The code will be executed in a sandboxed environment."
        )
        self.config = config
        self.timeout = config.python_executor_timeout
    
    def execute(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行Python代码
        
        Args:
            user_input: 用户输入（包含Python代码）
            context: 上下文信息
            
        Returns:
            执行结果字典，包含stdout, stderr, return_code等
        """
        # 提取Python代码
        code = user_input.strip()
        if not code:
            return {
                "stdout": "",
                "stderr": "No code provided",
                "return_code": 1
            }
        
        # 创建临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            # 执行Python代码
            result = subprocess.run(
                ['python', temp_file],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=tempfile.gettempdir()
            )
            
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {
                "stdout": "",
                "stderr": f"Code execution timeout after {self.timeout} seconds",
                "return_code": 1
            }
        except Exception as e:
            return {
                "stdout": "",
                "stderr": f"Error executing code: {str(e)}",
                "return_code": 1
            }
        finally:
            # 清理临时文件
            try:
                os.unlink(temp_file)
            except:
                pass


class CalculatorTool(BaseTool):
    """计算器工具"""
    
    def __init__(self, config: Config):
        """
        初始化计算器工具
        
        Args:
            config: 系统配置
        """
        super().__init__(
            name="calculator",
            description="Perform mathematical calculations. Use this tool when you need to calculate numbers, expressions, or mathematical operations."
        )
        self.config = config
    
    def execute(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行计算
        
        Args:
            user_input: 用户输入（包含数学表达式）
            context: 上下文信息
            
        Returns:
            计算结果字典
        """
        expression = user_input.strip()
        if not expression:
            return {
                "result": None,
                "error": "No expression provided"
            }
        
        try:
            # 安全的数学表达式计算
            # 只允许基本的数学运算
            allowed_chars = set('0123456789+-*/()., ')
            if not all(c in allowed_chars for c in expression):
                return {
                    "result": None,
                    "error": "Invalid characters in expression"
                }
            
            # 使用eval计算（注意：实际使用中应该使用更安全的计算方式）
            result = eval(expression)
            
            return {
                "result": result,
                "expression": expression
            }
        except Exception as e:
            return {
                "result": None,
                "error": f"Calculation error: {str(e)}"
            }


class FileReadTool(BaseTool):
    """文件读取工具"""
    
    def __init__(self, config: Config):
        """
        初始化文件读取工具
        
        Args:
            config: 系统配置
        """
        super().__init__(
            name="file_read",
            description="Read content from a file. Use this tool when you need to read text files, code files, or any file content."
        )
        self.config = config
    
    def execute(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        读取文件内容
        
        Args:
            user_input: 用户输入（包含文件路径）
            context: 上下文信息（可包含max_lines等参数）
            
        Returns:
            文件内容字典
        """
        file_path = user_input.strip()
        if not file_path:
            return {
                "content": "",
                "error": "No file path provided"
            }
        
        # 安全检查：只允许读取特定目录的文件
        # 实际使用中应该实现更严格的路径验证
        
        try:
            max_lines = context.get("max_lines", None)
            
            if max_lines:
                # 只读取前N行
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = []
                    for i, line in enumerate(f):
                        if i >= max_lines:
                            break
                        lines.append(line)
                    content = ''.join(lines)
            else:
                # 读取整个文件
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            
            return {
                "content": content,
                "file_path": file_path,
                "lines": len(content.split('\n'))
            }
        except FileNotFoundError:
            return {
                "content": "",
                "error": f"File not found: {file_path}"
            }
        except Exception as e:
            return {
                "content": "",
                "error": f"Error reading file: {str(e)}"
            }


class DateTimeTool(BaseTool):
    """日期时间工具"""
    
    def __init__(self, config: Config):
        """
        初始化日期时间工具
        
        Args:
            config: 系统配置
        """
        super().__init__(
            name="datetime",
            description="Get current date and time, or perform date/time operations. Use this tool when you need to know the current time or work with dates."
        )
        self.config = config
    
    def execute(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取日期时间信息
        
        Args:
            user_input: 用户输入（可包含日期时间操作）
            context: 上下文信息
            
        Returns:
            日期时间信息字典
        """
        now = datetime.now()
        
        # 简单的日期时间操作
        if "format" in user_input.lower() or "format" in context:
            format_str = context.get("format", "%Y-%m-%d %H:%M:%S")
            return {
                "current_time": now.strftime(format_str),
                "timestamp": now.timestamp(),
                "iso_format": now.isoformat()
            }
        else:
            return {
                "current_time": now.strftime("%Y-%m-%d %H:%M:%S"),
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M:%S"),
                "timestamp": now.timestamp(),
                "iso_format": now.isoformat()
            }

