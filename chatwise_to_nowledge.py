#!/usr/bin/env python
"""
ChatWise 导出文件导入 Nowledge Mem 工具

用法:
    python chatwise_to_nowledge.py <zip文件或解压目录> [--auto|--manual]

选项:
    --auto    自动模式，批量导入所有记录
    --manual  手动模式，逐个确认导入
    不指定时会交互式选择模式
"""

import argparse
import json
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

import requests
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from rich.table import Table

console = Console()

# Nowledge Mem API 配置
NOWLEDGE_MEM_API_BASE = "http://127.0.0.1:14242"
NOWLEDGE_MEM_API_THREADS = f"{NOWLEDGE_MEM_API_BASE}/threads"


def fetch_existing_threads() -> list[dict]:
    """获取服务端所有已存在的 threads"""
    all_threads = []
    limit = 100
    offset = 0

    try:
        while True:
            response = requests.get(
                NOWLEDGE_MEM_API_THREADS,
                params={"limit": limit, "offset": offset},
                timeout=30,
            )

            if response.status_code != 200:
                console.print(f"[yellow]警告: 获取已有记录失败 - {response.status_code}[/yellow]")
                break

            data = response.json()
            threads = data.get("threads", [])
            all_threads.extend(threads)

            pagination = data.get("pagination", {})
            if not pagination.get("has_more", False):
                break

            offset += limit

    except requests.exceptions.ConnectionError:
        console.print("[yellow]警告: 无法连接服务端，将跳过去重检查[/yellow]")
    except Exception as e:
        console.print(f"[yellow]警告: 获取已有记录时出错 - {e}[/yellow]")

    return all_threads


def is_chatwise_format(directory: Path) -> bool:
    """检查目录是否为 ChatWise 导出格式"""
    # 检查 chatwise-export-verison.txt 文件
    version_file = directory / "chatwise-export-verison.txt"
    if version_file.exists():
        return True

    # 检查是否存在 chat-xxx.json 格式的文件
    chat_files = list(directory.glob("chat-*.json"))
    if chat_files:
        # 验证文件结构
        try:
            with open(chat_files[0], "r", encoding="utf-8") as f:
                data = json.load(f)
                return all(key in data for key in ["id", "title", "messages"])
        except (json.JSONDecodeError, KeyError):
            return False

    return False


def extract_zip(zip_path: Path) -> Path:
    """解压 zip 文件到临时目录"""
    temp_dir = Path(tempfile.mkdtemp())
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(temp_dir)

    # 检查是否有单一子目录
    subdirs = [d for d in temp_dir.iterdir() if d.is_dir()]
    if len(subdirs) == 1:
        return subdirs[0]
    return temp_dir


def parse_chat_file(file_path: Path) -> dict | None:
    """解析 ChatWise 聊天记录文件"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        messages = []
        for msg in data.get("messages", []):
            content = msg.get("content", "").strip()
            if not content:
                continue
            messages.append({"content": content, "role": msg.get("role", "user")})

        if not messages:
            return None

        return {
            "thread_id": f"chatwise-{data['id']}",
            "title": data.get("title", "Untitled"),
            "messages": messages,
            "source": "chatwise",
            "import_date": datetime.now().isoformat(),
            "metadata": {
                "original_id": data["id"],
                "model": data.get("model"),
                "created_at": data.get("createdAt"),
                "updated_at": data.get("updatedAt"),
            },
        }
    except (json.JSONDecodeError, KeyError) as e:
        console.print(f"[red]解析文件失败: {file_path.name} - {e}[/red]")
        return None


def import_to_nowledge(thread_data: dict) -> tuple[bool, str]:
    """导入聊天记录到 Nowledge Mem"""
    try:
        response = requests.post(
            NOWLEDGE_MEM_API_THREADS,
            json=thread_data,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )

        if response.status_code == 200:
            result = response.json()
            return True, f"成功创建 Thread ID: {result.get('thread', {}).get('id', 'unknown')}"
        else:
            return False, f"API 错误 {response.status_code}: {response.text[:200]}"
    except requests.exceptions.ConnectionError:
        return False, "连接失败: 请确保 Nowledge Mem 服务正在运行 (http://127.0.0.1:14242)"
    except requests.exceptions.Timeout:
        return False, "请求超时"
    except Exception as e:
        return False, f"未知错误: {e}"


def display_chat_summary(chat_data: dict):
    """显示聊天记录摘要"""
    table = Table(show_header=False, box=None)
    table.add_column("属性", style="cyan")
    table.add_column("值")

    table.add_row("标题", chat_data["title"])
    table.add_row("消息数", str(len(chat_data["messages"])))
    table.add_row("模型", chat_data.get("metadata", {}).get("model", "N/A"))
    table.add_row("创建时间", chat_data.get("metadata", {}).get("created_at", "N/A")[:19])

    # 显示第一条消息预览
    first_msg = chat_data["messages"][0]["content"]
    preview = first_msg[:100] + "..." if len(first_msg) > 100 else first_msg
    table.add_row("首条消息", preview)

    console.print(Panel(table, title="聊天记录详情", border_style="blue"))


def manual_mode(chats: list[dict], existing_ids: set[str]):
    """手动模式: 逐个确认导入"""
    console.print(Panel("📋 手动模式: 逐个确认导入", style="green"))

    imported = 0
    skipped = 0
    duplicates = 0

    for i, chat in enumerate(chats, 1):
        # 基于 thread_id 去重检查
        if chat["thread_id"] in existing_ids:
            duplicates += 1
            console.print(f"\n[bold]({i}/{len(chats)})[/bold] [dim]{chat['title']}[/dim]")
            console.print("[yellow]⊘ 已存在，自动跳过[/yellow]")
            continue

        console.print(f"\n[bold]({i}/{len(chats)})[/bold]")
        display_chat_summary(chat)

        choice = Prompt.ask(
            "操作选择",
            choices=["y", "n", "q"],
            default="y",
        )

        if choice == "q":
            console.print("[yellow]已退出手动模式[/yellow]")
            break
        elif choice == "n":
            skipped += 1
            console.print("[dim]已跳过[/dim]")
            continue

        success, message = import_to_nowledge(chat)
        if success:
            imported += 1
            console.print(f"[green]✓ {message}[/green]")
        else:
            console.print(f"[red]✗ {message}[/red]")

    console.print(f"\n[bold]完成:[/bold] 导入 {imported} 条, 跳过 {skipped} 条, 重复 {duplicates} 条")


def auto_mode(chats: list[dict], existing_ids: set[str]):
    """自动模式: 批量导入所有记录"""
    console.print(Panel("🚀 自动模式: 批量导入所有记录", style="green"))

    success_count = 0
    fail_count = 0
    duplicate_count = 0
    errors = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("正在导入...", total=len(chats))

        for chat in chats:
            # 基于 thread_id 去重检查
            if chat["thread_id"] in existing_ids:
                duplicate_count += 1
                progress.advance(task)
                continue

            progress.update(task, description=f"正在导入: {chat['title'][:30]}...")
            success, message = import_to_nowledge(chat)

            if success:
                success_count += 1
            else:
                fail_count += 1
                errors.append((chat["title"], message))

            progress.advance(task)

    # 显示结果
    console.print(f"\n[bold green]✓ 成功: {success_count}[/bold green]")
    if duplicate_count > 0:
        console.print(f"[bold yellow]⊘ 重复跳过: {duplicate_count}[/bold yellow]")
    if fail_count > 0:
        console.print(f"[bold red]✗ 失败: {fail_count}[/bold red]")
        for title, error in errors[:5]:
            console.print(f"  [dim]- {title}: {error}[/dim]")
        if len(errors) > 5:
            console.print(f"  [dim]... 还有 {len(errors) - 5} 个错误[/dim]")


def main():
    console.print(
        Panel.fit(
            "[bold cyan]ChatWise → Nowledge Mem 导入工具[/bold cyan]",
            border_style="cyan",
        )
    )

    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description="ChatWise 导出文件导入 Nowledge Mem 工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("path", help="ChatWise 导出的 zip 文件或解压后的目录")
    parser.add_argument("--auto", action="store_true", help="自动模式，批量导入所有记录")
    parser.add_argument("--manual", action="store_true", help="手动模式，逐个确认导入")

    args = parser.parse_args()
    input_path = Path(args.path)

    if not input_path.exists():
        console.print(f"[red]路径不存在: {input_path}[/red]")
        sys.exit(1)

    # 处理 zip 文件或目录
    if input_path.suffix.lower() == ".zip":
        console.print(f"[cyan]正在解压: {input_path.name}[/cyan]")
        work_dir = extract_zip(input_path)
    elif input_path.is_dir():
        work_dir = input_path
    else:
        console.print("[red]请提供 zip 文件或目录路径[/red]")
        sys.exit(1)

    # 验证格式
    if not is_chatwise_format(work_dir):
        console.print("[red]错误: 不是有效的 ChatWise 导出格式[/red]")
        sys.exit(1)

    console.print("[green]✓ 检测到 ChatWise 导出格式[/green]")

    # 扫描聊天文件
    chat_files = sorted(work_dir.glob("chat-*.json"))
    console.print(f"[cyan]找到 {len(chat_files)} 个聊天记录文件[/cyan]")

    # 解析聊天记录
    chats = []
    for file in chat_files:
        chat = parse_chat_file(file)
        if chat:
            chats.append(chat)

    if not chats:
        console.print("[yellow]没有找到有效的聊天记录[/yellow]")
        sys.exit(0)

    console.print(f"[green]解析成功: {len(chats)} 个有效聊天记录[/green]\n")

    # 显示聊天列表
    table = Table(title="聊天记录列表")
    table.add_column("#", style="dim", width=4)
    table.add_column("标题", max_width=40)
    table.add_column("消息数", justify="right")
    table.add_column("创建时间")

    for i, chat in enumerate(chats, 1):
        created = chat.get("metadata", {}).get("created_at", "")[:10]
        table.add_row(str(i), chat["title"][:40], str(len(chat["messages"])), created)

    console.print(table)
    console.print()

    # 获取服务端已有记录用于去重 (基于 thread_id)
    console.print("[cyan]正在获取服务端已有记录...[/cyan]")
    existing_threads = fetch_existing_threads()
    existing_ids = {t.get("id", "") for t in existing_threads}
    console.print(f"[green]✓ 已获取 {len(existing_threads)} 条已有记录[/green]\n")

    # 确定导入模式
    if args.auto:
        mode = "2"
    elif args.manual:
        mode = "1"
    else:
        # 交互式选择模式
        console.print("[bold]导入模式选择:[/bold]")
        console.print("  [cyan]1[/cyan] - 手动模式 (逐个确认，输入 y=导入 / n=跳过 / q=退出)")
        console.print("  [cyan]2[/cyan] - 自动模式 (批量导入所有记录)")
        console.print("  [cyan]q[/cyan] - 退出")
        console.print()

        mode = Prompt.ask(
            "请选择",
            choices=["1", "2", "q"],
            default="1",
        )

        if mode == "q":
            console.print("[yellow]已取消[/yellow]")
            sys.exit(0)

    if mode == "1":
        manual_mode(chats, existing_ids)
    else:
        auto_mode(chats, existing_ids)


if __name__ == "__main__":
    main()

