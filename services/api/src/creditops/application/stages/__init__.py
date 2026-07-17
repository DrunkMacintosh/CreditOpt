"""Deterministic document-processing stage contracts.

These modules intentionally expose pure, bounded stage adapters.  Durable
checkpoint writes and worker dispatch remain in the task-runner layer; this
package never mutates workflow state or treats model output as confirmed fact.
"""
