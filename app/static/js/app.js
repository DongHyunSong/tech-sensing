document.addEventListener('DOMContentLoaded', () => {
    // --- 1. 모달 제어 관련 기능 ---
    const modal = document.getElementById('reportModal');
    const modalTitle = document.getElementById('modalTitle');
    const modalBody = document.getElementById('modalBody');
    const closeModalBtn = document.querySelector('.close-btn');
    const modalCloseBtn = document.getElementById('modalCloseBtn');
    
    // 모달 닫기 공통 함수
    const closeModal = () => {
        modal.style.display = 'none';
        document.body.style.overflow = 'auto'; // 스크롤 복구
    };

    if (closeModalBtn) closeModalBtn.addEventListener('click', closeModal);
    if (modalCloseBtn) modalCloseBtn.addEventListener('click', closeModal);
    
    // 모달 바깥 배경 클릭 시 닫기
    window.addEventListener('click', (e) => {
        if (e.target === modal) {
            closeModal();
        }
    });

    // 리포트 리스트 클릭 이벤트 바인딩
    const reportItems = document.querySelectorAll('.report-item');
    reportItems.forEach(item => {
        item.addEventListener('click', () => {
            const reportId = item.getAttribute('data-id');
            const date = item.querySelector('.report-date').textContent;
            const fullContent = item.querySelector('.report-full-content').innerHTML;
            
            modalTitle.innerHTML = `인사이트 리포트 (${date})`;
            modalBody.innerHTML = fullContent;
            
            modal.style.display = 'flex';
            document.body.style.overflow = 'hidden'; // 배경 스크롤 방지
        });
    });


    // --- 2. 로컬 스토리지에 크론 토큰 보관 기능 ---
    const cronTokenInput = document.getElementById('cronTokenInput');
    if (cronTokenInput) {
        // 이전에 저장된 토큰이 있다면 불러와서 채움
        const savedToken = localStorage.getItem('philtvtech_cron_token');
        if (savedToken) {
            cronTokenInput.value = savedToken;
        }

        // 토큰 변경 시 자동 저장
        cronTokenInput.addEventListener('input', (e) => {
            localStorage.setItem('philtvtech_cron_token', e.target.value.trim());
        });
    }


    // --- 3. 리포트 즉시 생성 수동 트리거 ---
    const triggerReportBtn = document.getElementById('triggerReportBtn');
    const loaderWrapper = document.getElementById('loaderWrapper');
    const loaderText = document.getElementById('loaderText');

    if (triggerReportBtn) {
        triggerReportBtn.addEventListener('click', async () => {
            const token = cronTokenInput ? cronTokenInput.value.trim() : '';
            if (!token) {
                alert('수동으로 리포트를 생성하고 전송하려면 크론 보안 토큰(Cron Secret Token)을 입력하셔야 합니다.');
                if (cronTokenInput) cronTokenInput.focus();
                return;
            }

            const confirmTrigger = confirm(
                "정말로 지금 리포트를 생성하여 텔레그램으로 즉시 발송하시겠습니까?\n" +
                "최근 7일간 수집된 센싱 노트를 취합하여 새로운 보고서가 작성됩니다."
            );

            if (!confirmTrigger) return;

            // 로더 노출
            loaderText.innerText = "Gemini AI가 필리핀 현지 센싱 자료를 취합 및 분석하는 중입니다...";
            loaderWrapper.style.display = 'flex';

            try {
                // 백엔드 크론 라우트 호출 (GET 방식 활용)
                const url = `/cron/send-report?token=${encodeURIComponent(token)}`;
                const response = await fetch(url, {
                    method: 'POST', // GET과 POST 모두 대응하므로 안전하게 POST 전송
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });

                const data = await response.json();

                if (response.ok && data.success) {
                    loaderText.innerText = "분석 완료! 텔레그램 구독자에게 발송하고 대시보드를 새로고침합니다.";
                    setTimeout(() => {
                        loaderWrapper.style.display = 'none';
                        alert(`리포트 발송 성공!\n분석 자료: ${data.notes_analyzed_count}개\n발송 성공 수: ${data.subscribers_sent_count}명`);
                        window.location.reload(); // 리포트 목록 갱신을 위해 새로고침
                    }, 1500);
                } else {
                    loaderWrapper.style.display = 'none';
                    const errMsg = data.detail || data.message || '인증 오류 또는 시스템 내부 에러가 발생했습니다.';
                    alert(`리포트 생성 실패: ${errMsg}`);
                }
            } catch (err) {
                loaderWrapper.style.display = 'none';
                alert(`네트워크 통신 오류가 발생했습니다: ${err.message}`);
            }
        });
    }
});
