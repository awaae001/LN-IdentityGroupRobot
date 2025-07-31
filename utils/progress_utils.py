def create_progress_bar(current: int, total: int, length: int = 20) -> str:
    """
    创建一个文本格式的进度条字符串。

    :param current: 当前进度。
    :param total: 总进度。
    :param length: 进度条的字符长度。
    :return: 表示进度的字符串。
    """
    if total == 0:
        percent = 0
    else:
        percent = 100 * (current / float(total))
    
    filled_length = int(length * current // total)
    bar = '█' * filled_length + '-' * (length - filled_length)
    
    return f'|{bar}| {percent:.1f}% ({current}/{total})'
