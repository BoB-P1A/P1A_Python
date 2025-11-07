import { useEffect, useRef, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";
// import { api } from "@/lib/api"; // (나중에 postMessage로 JSON 받아서 저장할 때 사용)

type GojsMessage =
    | { type: "combined-json"; payload: any }          // flow1.html이 생성한 combined.json 객체
    | { type: "toast"; payload: { level?: "info" | "error"; message: string } }
    | { type: string; payload?: any };                 // 확장 대비

export default function ProtectionFlowChart() {
    const { user } = useAuth();
    const iframeRef = useRef<HTMLIFrameElement>(null);

    const [taskIdx, setTaskIdx] = useState<number>(1); // 업무/테스크 인덱스
    const buildSrc = (idx: number) => `/gojs/flow1.html?task_idx=${idx}&ts=${Date.now()}`;
    const [src, setSrc] = useState<string>(buildSrc(taskIdx));

    const reloadIframe = () => setSrc(buildSrc(taskIdx)); // 캐시 무력화 포함

    // 부모(React) ← 자식(iframe:flow1.html) postMessage 수신
    useEffect(() => {
        const handler = async (ev: MessageEvent) => {
            // 보안상 origin 체크를 권장하지만, PoC이므로 생략 가능
            const data: GojsMessage = ev.data;
            if (!data || typeof data !== "object") return;

            if (data.type === "combined-json") {
                // 1) iframe 내부에서 '저장' 클릭 시 window.parent.postMessage(...)로 올려보내면 여기서 잡힘
                const combined = data.payload;
                console.log("[iframe→react] combined-json:", combined);

                // 2) 나중에 백엔드 저장 API 연결 (예시)
                // try {
                //   await api.lifecycle.flowCharts.save(user?.company as string, "현재업무명", "", combined, "");
                // } catch (e) {
                //   console.error(e);
                // }
            } else if (data.type === "toast") {
                console.log(`[iframe→react] ${data.payload?.level ?? "info"}: ${data.payload?.message}`);
            }
        };
        window.addEventListener("message", handler);
        return () => window.removeEventListener("message", handler);
    }, [user?.company]);

    // 부모(React) → 자식(iframe:flow1.html) postMessage 송신 (필요 시)
    const postToIframe = (msg: GojsMessage) => {
        const iframeWin = iframeRef.current?.contentWindow;
        if (!iframeWin) return;
        iframeWin.postMessage(msg, "*"); // PoC에선 *, 운영 전환 시 origin 고정
    };

    // (선택) flow1.html 쪽의 “흐름표에서 불러오기” 버튼을 원격 클릭시키고 싶다면:
    const triggerBuildAndLoad = () => {
        postToIframe({ type: "trigger-build-and-load" });
    };

    // (선택) flow1.html에서 만든 JSON을 요청하고 싶다면:
    const requestCombinedJson = () => {
        postToIframe({ type: "request-combined-json" });
    };

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold text-primary">개인정보 흐름도</h1>
                    <p className="text-muted-foreground mt-2">
                        PoC: GoJS 편집기를 iframe으로 임베드했습니다. (public/gojs/flow1.html)
                    </p>
                </div>
                <div className="flex gap-2">
                    <Button variant="outline" onClick={reloadIframe}>새로고침</Button>
                    <Button variant="outline" onClick={triggerBuildAndLoad}>엑셀→JSON 불러오기</Button>
                    <Button onClick={requestCombinedJson}>편집결과 JSON 받기</Button>
                </div>
            </div>

            <Card className="shadow-pia-card">
                <CardHeader>
                    <CardTitle>GoJS 편집기</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="w-full" style={{ height: "calc(100vh - 240px)" }}>
                        <iframe
                            ref={iframeRef}
                            src={src}
                            title="GoJS-Editor"
                            width="100%"
                            height="100%"
                            style={{ border: "1px solid var(--border)", borderRadius: 8, background: "#fff" }}
                        />
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
