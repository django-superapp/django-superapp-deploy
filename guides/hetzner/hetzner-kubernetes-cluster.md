# Hetzner
### Setup Wireguard
1. https://10.5.0.1:8443/webfig/#WireGuard.Peers.new
2. https://markeclaudio.github.io/mikrotik-wireguard-config-generator/
3. Install Wireguard
```bash
apt update
apt install wireguard-tools
```
4. Add the configuration in `/etc/wireguard/wg0.conf`
    - make sure to modify AllowedIPs to `AllowedIPs = 10.5.0.0/16`
    - delete DNS line
6. Run ```
   ln -s /usr/bin/resolvectl /usr/local/bin/resolvconf
   sudo systemctl enable wg-quick@wg0.service
   sudo systemctl daemon-reload
   sudo systemctl start wg-quick@wg0
```yaml
apiVersion: v1
kind: Secret
metadata:
   name: default-ingress-nginx-certificate
   namespace: kube-system
type: kubernetes.io/tls
data:
   tls.crt: >-
      LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSUZ1ekNDQTZPZ0F3SUJBZ0lVQ3I5WTJWUmwwUG5IN1JCclJ0VURjMldKWi9nd0RRWUpLb1pJaHZjTkFRRUwKQlFBd2JERUxNQWtHQTFVRUJoTUNXRmd4RWpBUUJnTlZCQWdNQ1ZOMFlYUmxUbUZ0WlRFUk1BOEdBMVVFQnd3SQpRMmwwZVU1aGJXVXhGREFTQmdOVkJBb01DME52YlhCaGJubE9ZVzFsTVE4d0RRWURWUVFMREFaellXMXdiR1V4CkR6QU5CZ05WQkFNTUJuTmhiWEJzWlRBZ0Z3MHlNekEzTURVeE5qQTJORGhhR0E4eU1USXpNRFl4TVRFMk1EWTAKT0Zvd2JERUxNQWtHQTFVRUJoTUNXRmd4RWpBUUJnTlZCQWdNQ1ZOMFlYUmxUbUZ0WlRFUk1BOEdBMVVFQnd3SQpRMmwwZVU1aGJXVXhGREFTQmdOVkJBb01DME52YlhCaGJubE9ZVzFsTVE4d0RRWURWUVFMREFaellXMXdiR1V4CkR6QU5CZ05WQkFNTUJuTmhiWEJzWlRDQ0FpSXdEUVlKS29aSWh2Y05BUUVCQlFBRGdnSVBBRENDQWdvQ2dnSUIKQUxVeGNXRmh3UC80V01jTFJ5ZjVEbUwvc2V0dnl1TU95dExiZ3B1UThQM1ViYkxjNFV3bWhRd0NqNXluc3A5VwpvNkdEcDdIWGk3cGFpeHZDS29iWHhWY1hqWWFvaHBFazh0WWYwbUtodzJxSW1ZcUIvV3dyVXVKa05zYjR6RSs2CkVoT3VBUXpXblJqYmFnRVk0WFlEZmlNUzFXRmcvR2ttU1Y2VHZFblFJKzBxNkUyZDMvSFNFVEpxdEZYZ1VZQTQKSHNZdXNFNkl5eWQzK0Z2R1h5eU1FOFBVNXdQcnpMeTkzVkdNZGVhelhIN0dnem85a01qYlk4aGphZ0p2bGVxRgpLR2EzNkQ3dTZ6bnlJQWVOYzhmYzZsbE42NnJhN1JjWUJ3RUxwSTdrdjlQYU85U0JlL29XM0pkUm53QnM2a01BCkhna0xtT2J1eGd3T2RTVFJIQ2M4Q3dFbDRZbFlTMlRuMGpqREJPMEc0TElZdGc4L0t1Wis3eDhRaWd1WklHY1AKNzQxczhmQmNHVWV0OGcralNnczExME1rMktSaTg3NzdGNHBtMVZGOHhoVXhuNEg1QTNOZ2RFRlN4dnBHNWQzNgpYTnRmSDFPU25ONXBnUk9sMThnY2M0TTFYMDlocXVKYWJNbk52WndtaEh3WEk2c3ZOLzJGTUhoZlBBVVdhOWpJCjBjL1VJZVc5TzNTMlJVN05WVGNTOFVCbnhpQXh1bC8wb1JPU3EwWFlwK0JiclZ3Y09mOTlRRjhVWG5MMUtDTzEKK0hGbzMyV2lvc3JKdURaWHhKZTBxZkcrZjREMFNtT1h3Wld6dEtWYzEvLzlVY3NUeVVuK1JidExoQVRDODkwSQpqbTRIano2Mkdpb1BCRUhhaFl4NjBBS3grL3BBQ2lSR081MDZxUXZ2ekRjSEFnTUJBQUdqVXpCUk1CMEdBMVVkCkRnUVdCQlJXRElTcHV0Z2pIN0UrK05aclk3N2dRdFBPSGpBZkJnTlZIU01FR0RBV2dCUldESVNwdXRnakg3RSsKK05aclk3N2dRdFBPSGpBUEJnTlZIUk1CQWY4RUJUQURBUUgvTUEwR0NTcUdTSWIzRFFFQkN3VUFBNElDQVFCTApiS1Y5eGhQZkNlLytxMFduTEkvbXIxRXJJQmJ2RzUvMVNkd0hPZkRZRDVGTzBwYVFwL0dNRngrdHNPQzR0cDI5ClRKQ1hNSkEwck5KaGhNM1ZvcmpRa3NwWXQ4SkdoMzhKR1pUSk5XcHlBVi8zZXZVc0taeHVtNmI5QWRJVGI1YW0KK1dTZkVrYzcrK1AxaHloQTg0eTJOMFNFbGZEVXQ0TTBYbHlXcldkOEFTaW9lTitaVE5aODZiQjlDRnREZUI2aQpUMXhKQ1VVOHBiUHZqNTJKNkJ2L21SWjVET29lOWJkaFJ5NjdoVmlSL2l4OThBa0xOTHRyNWFCaWF6bHlrRk11Cm5jczNPMkhvR3ZmSmlJL1JUaHRmckdtRTlPRWtnSmZ2WlFoSG5wb2piakFFSmlOZEJMSGhDWVVsRlRjRUt4ZjkKL282YlpXaEl6T0tLYmRRZEJzRFNKMXRHWVpsL1R2eDh1WWE2L2ZkV1JhbDNUMDAxUmpLQVJXNmZjU25qWlUyQgpyaVhDRTV0a3RTVy9HVi9uTGNPWnFSeGF5VjkrSVJFei9ydDFjSThmNDRKamo0Z2orL1lBc2gwVFZtZktLVXZpCkpXa09UdDZPY1QzVml1djEycEZuTHZEb1Z0TmI4a0dFVGJFMytyVlRLYWN4WW9pMGJpaTh3dE1NdS9meXA0NCsKb205cGJyaEQrTUVYMFQ1b3B6V2JKeFUwejhlaWlpeThnRnlCeVlhVlMxa3NhQWNtdWZEc0pRR2ZXQjl1cjRjYQptL1hWRE9CZUVrWHVjRVF5YzRtQkExSjh6UVNFa2crUTZpTUY4OVhzMlJtRVVhTEpkSURPRzJhL2ZmY1g4ZGJECmhseVp1TTJkSmJZZnNSWmtHVVlvVjRmUlQrOW5QVGU2QytMcmxWMWhldz09Ci0tLS0tRU5EIENFUlRJRklDQVRFLS0tLS0=
   tls.key: >-
      LS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tCk1JSUpRZ0lCQURBTkJna3Foa2lHOXcwQkFRRUZBQVNDQ1N3d2dna29BZ0VBQW9JQ0FRQzFNWEZoWWNELytGakgKQzBjbitRNWkvN0hyYjhyakRzclMyNEtia1BEOTFHMnkzT0ZNSm9VTUFvK2NwN0tmVnFPaGc2ZXgxNHU2V29zYgp3aXFHMThWWEY0MkdxSWFSSlBMV0g5SmlvY05xaUptS2dmMXNLMUxpWkRiRytNeFB1aElUcmdFTTFwMFkyMm9CCkdPRjJBMzRqRXRWaFlQeHBKa2xlazd4SjBDUHRLdWhObmQveDBoRXlhclJWNEZHQU9CN0dMckJPaU1zbmQvaGIKeGw4c2pCUEQxT2NENjh5OHZkMVJqSFhtczF4K3hvTTZQWkRJMjJQSVkyb0NiNVhxaFNobXQrZys3dXM1OGlBSApqWFBIM09wWlRldXEydTBYR0FjQkM2U081TC9UMmp2VWdYdjZGdHlYVVo4QWJPcERBQjRKQzVqbTdzWU1EblVrCjBSd25QQXNCSmVHSldFdGs1OUk0d3dUdEJ1Q3lHTFlQUHlybWZ1OGZFSW9MbVNCbkQrK05iUEh3WEJsSHJmSVAKbzBvTE5kZERKTmlrWXZPKyt4ZUtadFZSZk1ZVk1aK0IrUU56WUhSQlVzYjZSdVhkK2x6Ylh4OVRrcHplYVlFVApwZGZJSEhPRE5WOVBZYXJpV216SnpiMmNKb1I4RnlPckx6ZjloVEI0WHp3RkZtdll5TkhQMUNIbHZUdDB0a1ZPCnpWVTNFdkZBWjhZZ01icGY5S0VUa3F0RjJLZmdXNjFjSERuL2ZVQmZGRjV5OVNnanRmaHhhTjlsb3FMS3liZzIKVjhTWHRLbnh2bitBOUVwamw4R1ZzN1NsWE5mLy9WSExFOGxKL2tXN1M0UUV3dlBkQ0k1dUI0OCt0aG9xRHdSQgoyb1dNZXRBQ3NmdjZRQW9rUmp1ZE9xa0w3OHczQndJREFRQUJBb0lDQUN1c3VFeWwySFNhc3lOL1IyNk9MUGFWCjlaZnZnWE1Mbkw0SXBVbkVQU0toOHJNN1pKOExaZVNJTlgrb09Ia0oxRFZaVzdHVmFCdktPVisraEt1dUZPWXkKU2kzY0wxdUxFWEdsaC91NFREZEFwK25uL1dMMmFtc2hoc2FkTC9wRHVwbTl4b2tHcmlWUXRoTi9vTkRtZEtBVgpxUk5vNGs2aUtPdEFKeEdQdHlreXYzMytBUDMwQ2FzaVowZVA0M1ZKa2JscGhadllnMGVITm5sQXJxNDVNWVp4CnFpR2EwK1hteWhNZkRVaEhrWk1KWEpaTVFycjNqdXk5Y2M4V2dJZGdBMllIREZjbkZkSUkxOG1hUWY4NTg4OEUKNWpwdnZOaGxOVUwrUUhNbEZrd0ZmWWh5a2FTdG9BeGxZek1pRGJHS3RMS3ZkZktzT1Zhc29YWDNaWmJiZFRjdwpGbXF2cE5XUDhlRk9xelE3eTFsZDNNdmNsZHZaY1plY3Z4Q0xuRFlhWDh6akk3YUpNcHpYT01FU2tYR0hiM2NOClgyYmt2RWhZM0tUOWhzWTZrejJ0YmFZSXAwUHhCMWNHWDRudWRiQ3Y3QnpLdTFQbEo2Mk5LM0ZUYW9HMDRMY3UKd05KMWtoR3dTdTd4MU5FaTRzK05pZDlVVnlPZFlOcjlwamtlYXRhbkJaeklGdFNzMlBIV2FFbWxIeWY2ekYrbQpyT0pjNmVrYStCVWJTVGNxNkJXTElTSkc0clhvWlhFYjZsSEpxWHZiVmNLVW1uRUhKV3MxNXdtOWEvUW9aS3IzClZZNnZBUWc1UWIzNnIvNHBEK2NtWGhDTld6Ujd4Sko1dUhDNm96MUZqUVV1WDNWMCthTCsyZXNUN0s0NWRhamoKR09peWhacU1tM1RuTE5pRGkxVXBBb0lCQVFEeUFmb3VKcVdWaEo1SVlaNnFjcXM3T3ZUUDZsS3I5aWFmd3lpbApuNEQ3Ni82eHk1TmdQcExkanFxVGRJQzZKTUp0ZysrLysvTTgxUjZKQXlvdkk4eWUvOGhMSm5nUzgvSGZPdlg2CnRTVE5FRmw2bnpiYTRCSVU0QkQrWWRHSy80dERZamJsYlUxdTliN0p5MHZyL3hLUkUyZHdsRCtqQWE5UnZaL2cKOUg1cEZhV21hZlNrM3Nwbi9wNEYvazdtMW02bFp4Sm9HKytXMURiK2swakN1ekN3aXk2bkJaYk04ZTVCcVV1SwpRQTNvK2RSQTc3RWwvVnF4ZHVZRGoyWTh5MWRFKzRtQVV2MlVRd3N3T2hvY0RmaW01dS8rSmdqZzgvR1djTkVkCjJWeFZBVVdHVjJLYndSVzVEdXpYTjBaSVVaNFA4RmxLd21IR3dYUXY0YU5JZ3ZPTEFvSUJBUUMvcTFVTTRrMFAKTUVSbTlMMnBSSERNUEVkUlk4MG5sMUNIVzBiTW1RaVdMYzBqeThOT3RoQ1d6TkxkcHpsSFlyc2JpZncvT0RZNgpXSStFSEVndHhCM2dWenJwK3kza1VuOEpJYnhIcUt6RkRTb1BpbVNBTVF1MmsyTytoaXF5QlBtd0dMa0hKWDc0CnRndnRQeEJOWXFUaEVUMDEyMCs5NkRBUVJ4SzZac290d0t4UWdJVzgvQlcrUldTcnBiYVJVYnVmSWJMa3drVHIKenBRRkgyTWhZTG91dGtwTnNoWTNkSnpwcWY0OVRMS0hOQWRwQ0s4UWtGVVhTNE5ONktVT3Bqd0hRZW1LRzUxRgpKTTZKcTNCUmgwNkdRTDBkRUZZL1FNenRjSUdnQS9aVE9IU3llUTdGVlBLT0xVNngvV3dJK2hHVlMzK1ZjNkNQClc4eUh2cFR2NDhuMUFvSUJBR20vWFcrZktZbWRDb0Q4VHhXUng2cTVCMUoyeEtzcGd4VWFkUDl5SkMxd29MbFcKQ0U3czZNWHhXaTNXb1kwMUZOUS82NXBMWUt6N1B6MkZhWUJ4dHk3ZSs4bUN4TU1iWDF3NDZsVWpwRElLNjk1KwpCYjA4WGdwTElvSFZnbmVuVkZZY2EzcHkrWHY3MitOWGR4Um5QOWl1enV0TmpFVVJMbWVjWVdrdHpMTGtaNTdBCis4cXpJMlN2eUtNN3pZUm12TEIveW5ZOWhzSzBkbGRsU2t6MCtNQ2NBTVd3MW9VMVRmUFpJdzRGRVU3MUk3OUEKUFhzcEt1RVM0RTA3OHVPcndyVjg2RWR2ZkNpMTV3U3F6cy9sZHZxUFBOMGtCNHNzYlN0Y25yUFpUOVJCR3YwcAo0QWZKSmxIWDZMdmVCbE1CZnZ6ZC9GYURlN0FheGtkSjVFeUNGQ01DZ2dFQkFLUTlUbTN4NVJKa3k5aGxVN2dkCis0SW5EUDNEUldMdG1JWEVRMURDdWNibWpHaG1ESUFBSndyeGpLZCt5ZWhQeEFGL0pmV09WM2w3dGM4QTVTREMKY3M5d0wvMmJ6T0ZmaDVmdG5vYlJGT3J0c3VNS05jQmJScXcyZER3b2Y2RjMvZlZWMmdjenJDKzIzMVYydXFOMQpLYy9xazhiNG5NWWdsajc4aUNIT1B1VWh1d1pvZXpGTDJkM25YTEp4RjVaQ3NVRlZBUlJoRytuc1pJNVhMUHpICkJBTlBGVENxcjdycFpDUWVGTXUyVXl6aitvMlljVnNDTXNmNVh4UjlqQ0tYYzh6TVFEQ21KUWZBMkhMRHcwVTUKYXFKRUMwbENYSVZySTY4NnZ2aTlMSEIzYWhnYy8vazhKM1NKZ211bXV0S2VaajdHS1JlSnMwWGs1Y2hVR1EvTwo0NWtDZ2dFQVV5Qzk2Z3djWjdVQjJ6R0wzeExnUW5SR01OTUZFTms2Ni8vZHltU0V0N004QjFsdjBYbFp0NS9MCmVFSUtyR1VqYUpGbnFCWXcrWWttdHU0NkpDaVNxdGVmazA3dHJZanM4WnM0aTJXSUFWbmU2U0NMSDVYQTAveFQKMy9XOVdJSzZKTDZ6R0F0dWVVL1VwSjBjK3RZQkhRTlg3c2VlUExlZklNK1Bmb3YxblByQlp3d1kzRSsxaVhyVgpDODZpSjJtY2creVN2cTIvWEx3OFF6d0pCcWczeXdJR0xiWkVhdDgyVllvNVpZQjdaVUxHMHJWdWxJbmZuYWlnClF3K3dEU2V5NWRNYXdhYk5Qc1VKL3dSK1lhN2NjTEJvREk0RHNPU1JneDJpOUdNa3NyOG5QUXZ6SnpUVE9DUU4KSGx5R2l3VjBoSTltTXJrQkIyNHNYTThKaXNVQ3lnPT0KLS0tLS1FTkQgUFJJVkFURSBLRVktLS0tLQ==
---
apiVersion: v1
kind: Namespace
metadata:
   name: ingress-nginx
---
apiVersion: helm.cattle.io/v1
kind: HelmChart
metadata:
   name: ingress-nginx
   namespace: kube-system
spec:
   chart: ingress-nginx
   repo: https://kubernetes.github.io/ingress-nginx
   targetNamespace: ingress-nginx
   version: v4.11.1
   valuesContent: |-
      fullnameOverride: ingress-nginx
      controller:
        kind: Deployment
        replicaCount: 1
        ingressClassResource:
          enabled: 'true'
          default: 'true'
          name: nginx
        ingressClassByName: 'true'
        publishService:
          enabled: true
        hostPort:
          enabled: true
        service:
          enabled: false
          type: NodePort
          nodePorts:
            http: '31080'
            https: '31443'
        metrics:
          enabled: false
          serviceMonitor:
            enabled: false
        config:
          use-proxy-protocol: 'false'
          log-format-upstream: '{"time": "$time_iso8601", "namespace": "$namespace", "ingress_name":
            "$ingress_name", "service_name": "$service_name",  "service_port": "$service_port",
            "remote_addr": "$proxy_protocol_addr", "x_forwarded_for": "$proxy_add_x_forwarded_for",
            "request_id": "$req_id", "remote_user": "$remote_user", "bytes_sent": $bytes_sent,
            "request_time": $request_time, "status": $status, "vhost": "$host", "request_proto":
            "$server_protocol", "path": "$uri", "request_query": "$args", "request_length":
            $request_length, "duration": $request_time,"method": "$request_method", "http_referrer":
            "$http_referer","http_user_agent": "$http_user_agent", "proxy_upstream_name":
            "$proxy_upstream_name", "proxy_alternative_upstream_name": "$proxy_alternative_upstream_name",
            "upstream_addr": "$upstream_addr", "upstream_response_length": $upstream_response_length,
            "upstream_response_time": $upstream_response_time, "upstream_status": $upstream_status
            }'
          log-format-stream: '{"time": "$time_iso8601", "remote_addr": "$remote_addr", "protocol":
            "$protocol", "status": $status, "bytes_sent": $bytes_sent,  "bytes_received":
            $bytes_received, "session_time": $session_time , "upstream_addr": "$upstream_addr",
            "upstream_bytes_sent": $upstream_bytes_sent, "upstream_bytes_received": $upstream_bytes_received,
            "upstream_connect_time": "$upstream_connect_time" }'
          limit-req-status-code: '429'
          limit-conn-status-code: '429'
        extraArgs:
          default-ssl-certificate: "kube-system/default-ingress-nginx-certificate"
        containerSecurityContext:
          runAsNonRoot: false
          allowPrivilegeEscalation: false
        resources:
          limits:
            cpu: 1000m
            memory: 1024Mi
          requests:
            cpu: 100m
            memory: 128Mi
```



