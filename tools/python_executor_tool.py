"""Python代码执行工具"""
from typing import Dict, Any, Optional
import json
import traceback
from .base import BaseTool
# 处理相对导入问题
try:
    from ..config.config import Config
except (ImportError, ValueError):
    # 如果相对导入失败，使用绝对导入
    import sys
    from pathlib import Path
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from config.config import Config


class PythonExecutorTool(BaseTool):
    """Python代码执行工具，用于执行计算、公式等"""
    
    def __init__(self, config: Optional[Config] = None):
        """
        初始化Python执行工具
        
        Args:
            config: 系统配置
        """
        super().__init__(
            name="python_executor",
            description="Execute Python code to perform calculations, data processing, or formula evaluation. Input should be a JSON string with 'code' field containing the Python code to execute. The code should return a result that can be serialized to JSON."
        )
        self.config = config
        # 安全的执行环境（可以限制可用的模块）
        self.allowed_modules = {
            'math', 'random', 'datetime', 'json', 're', 'collections',
            'itertools', 'functools', 'operator', 'decimal', 'fractions'
        }
    
    def execute(self, code: str, **kwargs) -> str:
        """
        执行Python代码
        
        Args:
            code: Python代码字符串
            **kwargs: 其他参数（如输入参数等）
            
        Returns:
            执行结果（JSON字符串）
        """
        try:
            # 解析输入参数（如果有）
            input_params = kwargs.get('params', {})
            if isinstance(input_params, str):
                try:
                    input_params = json.loads(input_params)
                except:
                    input_params = {}
            
            # 创建安全的执行环境
            safe_globals = {
                '__builtins__': {
                    'abs': abs, 'all': all, 'any': any, 'bool': bool,
                    'dict': dict, 'float': float, 'int': int, 'len': len,
                    'list': list, 'max': max, 'min': min, 'range': range,
                    'round': round, 'str': str, 'sum': sum, 'tuple': tuple,
                    'type': type, 'zip': zip, 'enumerate': enumerate,
                    'print': print, 'json': json
                },
                'params': input_params,
                'result': None
            }
            
            # 导入允许的模块
            import importlib
            for module_name in self.allowed_modules:
                try:
                    safe_globals[module_name] = importlib.import_module(module_name)
                except:
                    pass
            
            # 执行代码
            exec(code, safe_globals)
            
            # 获取结果
            result = safe_globals.get('result')
            if result is None:
                # 如果没有设置result，尝试获取最后一个表达式的值
                # 这里简化处理，返回执行成功的信息
                result = {"status": "success", "message": "Code executed successfully"}
            
            # 序列化结果
            if isinstance(result, (dict, list, str, int, float, bool, type(None))):
                return json.dumps(result, ensure_ascii=False, indent=2)
            else:
                return json.dumps({"status": "success", "result": str(result)}, ensure_ascii=False)
                
        except Exception as e:
            error_msg = f"Error executing Python code: {str(e)}\n{traceback.format_exc()}"
            return json.dumps({
                "status": "error",
                "error": error_msg
            }, ensure_ascii=False)
    
    def to_param(self) -> Dict[str, Any]:
        """转换为工具参数格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "Python code to execute. The code should set a variable 'result' with the final result, or return a value."
                        },
                        "params": {
                            "type": "object",
                            "description": "Input parameters as a dictionary (optional)"
                        }
                    },
                    "required": ["code"]
                }
            }
        }

