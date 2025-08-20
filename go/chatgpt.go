package main

import (
	"context"
	"fmt"
	"os"
	"time"

	openai "github.com/sashabaranov/go-openai"
)

type GPT struct{ cli *openai.Client }

func NewGPT() (*GPT, error) {
	key := os.Getenv("OPENAI_API_KEY")
	if key == "" {
		return nil, fmt.Errorf("OPENAI_API_KEY not set")
	}
	return &GPT{cli: openai.NewClient(key)}, nil
}

func (g *GPT) Ask(q string) (string, error) {
	// Create context with timeout to prevent hanging
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	
	resp, err := g.cli.CreateChatCompletion(ctx,
		openai.ChatCompletionRequest{
			Model: openai.GPT4Dot1Nano,
			Messages: []openai.ChatCompletionMessage{
				{Role: "system", Content: "You are a fantasy football expert. Give a summary of who to draft and why."},
				{Role: "user", Content: q},
			},
		})
	if err != nil {
		return "", err
	}
	if len(resp.Choices) == 0 {
		return "", fmt.Errorf("empty response")
	}
	return resp.Choices[0].Message.Content, nil
}
