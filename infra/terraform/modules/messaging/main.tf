variable "project_name" { type = string }
variable "environment" { type = string }

resource "aws_sqs_queue" "recurring_dlq" {
  name = "${var.project_name}-${var.environment}-recurring-dlq"
}

resource "aws_sqs_queue" "recurring" {
  name                       = "${var.project_name}-${var.environment}-recurring"
  visibility_timeout_seconds = 60
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.recurring_dlq.arn
    maxReceiveCount     = 3
  })
}

resource "aws_cloudwatch_event_bus" "this" {
  name = "${var.project_name}-${var.environment}"
}

resource "aws_cloudwatch_event_rule" "recurring" {
  name                = "${var.project_name}-${var.environment}-recurring"
  schedule_expression = "rate(1 day)"
}

output "recurring_queue_arn" { value = aws_sqs_queue.recurring.arn }
output "recurring_queue_url" { value = aws_sqs_queue.recurring.url }
output "event_bus_name" { value = aws_cloudwatch_event_bus.this.name }
