def calculate_stats(numbers):
    total = sum(numbers)
    count = len(numbers)
    mean = total / count
    return {"total": total, "count": count, "mean": mean}
