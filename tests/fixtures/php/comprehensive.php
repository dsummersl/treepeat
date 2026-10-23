<?php
declare(strict_types=1);

namespace Example;

use DateTimeImmutable;
use Example\Contracts\{Serializable, Countable};
use function array_sum;
use const PHP_VERSION;

/** Calculate a total with a minimum value. */
function total(array $values, int $minimum = 0): int
{
    $sum = 0;
    foreach ($values as $value) {
        if ($value > $minimum) {
            $sum += $value;
        }
    }
    return $sum;
}

interface Formatter
{
    public function format(string $value): string;
}

trait HasLabel
{
    public function label(): string
    {
        return 'example';
    }
}

enum Status: string
{
    case Active = 'active';
    case Inactive = 'inactive';
}

#[\AllowDynamicProperties]
final class Report implements Formatter
{
    use HasLabel;

    public function __construct(private readonly string $prefix = '')
    {
    }

    public function format(string $value): string
    {
        // Keep interpolation as an expression.
        $message = "{$this->prefix}: $value";
        return $message;
    }
}

$offset = 1;
$increment = function (int $value) use ($offset): int {
    return $value + $offset;
};
$double = fn (int $value): int => $value * 2;
$worker = new class {
    public function run(): bool
    {
        return true;
    }
};
