"""
从Docker容器提取日志文件到本地目录
"""

import subprocess
import sys
import argparse
from pathlib import Path
from datetime import datetime


def extract_logs_from_docker(container_name: str, local_dir: str = "./logs"):
    """
    从Docker容器提取日志文件
    
    Args:
        container_name: 容器名称
        local_dir: 本地保存目录
    """
    print(f"正在从容器 '{container_name}' 提取日志文件...")
    
    # 创建本地目录
    local_path = Path(local_dir)
    local_path.mkdir(parents=True, exist_ok=True)
    
    # 检查容器是否存在
    try:
        result = subprocess.run(
            ['docker', 'ps', '-a', '--filter', f'name={container_name}', '--format', '{{.Names}}'],
            capture_output=True,
            text=True,
            check=True
        )
        
        if container_name not in result.stdout:
            print(f"错误: 容器 '{container_name}' 不存在")
            print("请先启动容器: docker-compose up -d")
            return False
    except subprocess.CalledProcessError as e:
        print(f"错误: 无法检查容器状态: {e}")
        return False
    
    # 提取日志文件
    try:
        # 创建临时目录
        temp_dir = local_path / "temp_extract"
        temp_dir.mkdir(exist_ok=True)
        
        # 从容器复制日志目录
        print(f"正在复制日志文件到临时目录: {temp_dir}")
        result = subprocess.run(
            ['docker', 'cp', f'{container_name}:/app/logs/.', str(temp_dir)],
            capture_output=True,
            text=True,
            check=True
        )
        
        print("日志文件复制成功")
        
        # 显示提取的文件
        print("\n提取的文件:")
        for file_path in temp_dir.rglob('*'):
            if file_path.is_file():
                relative_path = file_path.relative_to(temp_dir)
                print(f"  - {relative_path}")
        
        # 询问是否移动到主目录
        print(f"\n日志文件已提取到: {temp_dir}")
        print(f"您可以直接使用此目录进行分析，或移动到: {local_path}")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"错误: 无法提取日志文件: {e}")
        print(f"stderr: {e.stderr}")
        return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='从Docker容器提取日志文件')
    parser.add_argument('--container', type=str, default='binance-telegram-bot', help='容器名称')
    parser.add_argument('--local-dir', type=str, default='./logs', help='本地保存目录')
    
    args = parser.parse_args()
    
    success = extract_logs_from_docker(args.container, args.local_dir)
    
    if success:
        print("\n✓ 日志提取成功！")
        print(f"\n现在可以使用以下命令分析数据:")
        print(f"python analyze_trades.py --data-dir {args.local_dir}/temp_extract/trades")
    else:
        print("\n✗ 日志提取失败")
        sys.exit(1)


if __name__ == '__main__':
    main()